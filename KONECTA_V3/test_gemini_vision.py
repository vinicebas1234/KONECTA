import asyncio
import os
import numpy as np
from app_central.motors.motor_gemini_vision import MotorGeminiVision

async def test_motor_gemini_vision():
    print("🚀 Testando Motor Gemini Vision...")
    
    # Mock API key
    api_key = os.getenv("ANTHROPIC_API_KEY", "sk-test")
    motor = MotorGeminiVision(api_key=api_key)
    
    # Mock frame (1x1 pixels para velocidade)
    frame_b64 = "base64dummy"
    
    result = await motor.validate(frame_b64)
    
    print(f"✅ Resultado: {result}")
    
    assert result.status == "success"
    assert 0 <= result.quality_score <= 100
    assert result.latency_ms < 300
    print("✅ Teste passou!")

if __name__ == "__main__":
    asyncio.run(test_motor_gemini_vision())
