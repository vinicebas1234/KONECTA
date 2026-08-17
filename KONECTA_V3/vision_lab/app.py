"""FastAPI application for Vision Lab."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from vision_lab.dataset import DatasetLoader, VideoLoader
from vision_lab.landmarks import LandmarkExtractor
from vision_lab.visualization import LandmarkVisualizer, QualityAnalyzer
from vision_lab.temporal import TemporalAnalyzer
from vision_lab.core import LandmarkConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KONECTA V3 — Vision Lab",
    description="Experimental vision pipeline for Libras recognition research",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class DatasetDiscoveryRequest(BaseModel):
    path: str

# State
dataset_loader = DatasetLoader()
landmark_extractor = LandmarkExtractor()
quality_analyzer = QualityAnalyzer()
temporal_analyzer = TemporalAnalyzer()
current_dataset = None
current_video_frames = {}  # Cache for extracted frames


@app.get("/")
async def root():
    """Serve dashboard."""
    web_dir = Path(__file__).parent / "web"
    if (web_dir / "index.html").exists():
        return FileResponse(web_dir / "index.html")
    return {"message": "Vision Lab API"}


@app.post("/api/datasets/discover")
async def discover_dataset(request: DatasetDiscoveryRequest = Body(...)):
    """Discover dataset at path."""
    global current_dataset
    try:
        current_dataset = dataset_loader.discover_dataset(Path(request.path))
        return {
            "name": current_dataset.name,
            "videos": len(current_dataset.videos),
            "classes": len(current_dataset.classes),
            "signers": len(current_dataset.signers),
        }
    except Exception as e:
        logger.error(f"Dataset discovery failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/datasets/current")
async def get_current_dataset():
    """Get current dataset info."""
    if not current_dataset:
        raise HTTPException(status_code=404, detail="No dataset loaded")

    return {
        "name": current_dataset.name,
        "videos": len(current_dataset.videos),
        "classes": current_dataset.classes,
        "signers": current_dataset.signers,
        "class_distribution": {
            cls: len(current_dataset.get_videos_by_class(cls))
            for cls in current_dataset.classes[:10]  # Top 10
        },
    }


@app.get("/api/videos/{video_id}/info")
async def get_video_info(video_id: str):
    """Get info about a video."""
    if not current_dataset:
        raise HTTPException(status_code=404, detail="No dataset loaded")

    for video in current_dataset.videos:
        if video.id == video_id:
            return {
                "id": video.id,
                "class": video.class_name,
                "signer": video.signer_id,
                "fps": video.fps,
                "frames": video.total_frames,
                "width": video.width,
                "height": video.height,
                "duration_s": video.duration_s,
            }

    raise HTTPException(status_code=404, detail="Video not found")


@app.get("/api/videos/{video_id}/frame/{frame_id}")
async def get_video_frame(video_id: str, frame_id: int, with_landmarks: bool = False):
    """Get frame from video (returns base64 image).

    Args:
        video_id: Video ID
        frame_id: Frame number
        with_landmarks: If true, overlay landmarks on frame
    """
    if not current_dataset:
        raise HTTPException(status_code=404, detail="No dataset loaded")

    video = next((v for v in current_dataset.videos if v.id == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        # Get cached frames if available
        if video_id in current_video_frames and frame_id < len(current_video_frames[video_id]):
            frame = current_video_frames[video_id][frame_id]
            image = frame.image
        else:
            # Load from disk
            with VideoLoader(video) as loader:
                image = loader.get_frame(frame_id)
                if image is None:
                    raise HTTPException(status_code=404, detail="Frame not found")

        # Draw landmarks if requested
        if with_landmarks and video_id in current_video_frames:
            frame = current_video_frames[video_id][frame_id]
            if frame.landmarks is not None:
                image = LandmarkVisualizer.draw_landmarks(frame, frame.landmarks)

        import base64
        import cv2

        _, buffer = cv2.imencode(".jpg", image)
        image_b64 = base64.b64encode(buffer).decode()

        return {"frame_id": frame_id, "image": f"data:image/jpeg;base64,{image_b64}"}
    except Exception as e:
        logger.error(f"Frame retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/videos/{video_id}/extract-landmarks")
async def extract_landmarks(video_id: str):
    """Extract landmarks from entire video and cache frames."""
    global current_video_frames

    if not current_dataset:
        raise HTTPException(status_code=404, detail="No dataset loaded")

    video = next((v for v in current_dataset.videos if v.id == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        extractor = LandmarkExtractor(LandmarkConfig())
        frame_count = 0
        valid_frames = 0
        quality_scores = []
        frames_list = []

        with VideoLoader(video) as loader:
            for frame in loader.iter_frames():
                frame = extractor.extract(frame)

                # Analyze quality
                quality = quality_analyzer.analyze_frame(frame)
                frame.quality_score = quality["score"] / 100.0

                frame_count += 1

                if frame.landmarks is not None:
                    valid_frames += 1
                    quality_scores.append(frame.confidence or 0.0)

                frames_list.append(frame)

        # Cache frames
        current_video_frames[video_id] = frames_list
        video.frames = frames_list

        avg_confidence = (
            sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        )

        return {
            "video_id": video_id,
            "total_frames": frame_count,
            "valid_frames": valid_frames,
            "detection_rate": valid_frames / max(frame_count, 1),
            "avg_confidence": avg_confidence,
        }
    except Exception as e:
        logger.error(f"Landmark extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos/{video_id}/quality")
async def get_quality_report(video_id: str):
    """Get quality analysis for each frame."""
    if video_id not in current_video_frames:
        raise HTTPException(status_code=404, detail="Video not processed. Extract landmarks first.")

    frames = current_video_frames[video_id]
    report = []

    for frame_id, frame in enumerate(frames):
        quality = quality_analyzer.analyze_frame(frame)
        report.append({
            "frame_id": frame_id,
            "timestamp": frame.timestamp,
            **quality,
        })

    return {"video_id": video_id, "frames": report}


@app.get("/api/videos/{video_id}/temporal")
async def get_temporal_analysis(video_id: str):
    """Get temporal consistency analysis."""
    if video_id not in current_video_frames:
        raise HTTPException(status_code=404, detail="Video not processed. Extract landmarks first.")

    frames = current_video_frames[video_id]
    temp_analyzer = TemporalAnalyzer(window_size=len(frames))

    for frame in frames:
        temp_analyzer.add_frame(frame)

    return temp_analyzer.get_report()


# Serve static files (if web directory exists)
web_dir = Path(__file__).parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=web_dir), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
