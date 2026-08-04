/* Cliente da API do SIGNLAB */
const api = (() => {
  async function request(method, url, body) {
    const opts = { method, headers: {} };
    if (body instanceof FormData) {
      opts.body = body;
    } else if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  return {
    listProjects: () => request('GET', '/api/projects'),
    createProject: (name) => request('POST', '/api/projects', { name }),
    getProject: (id) => request('GET', `/api/projects/${id}`),
    renameProject: (id, name) => request('PATCH', `/api/projects/${id}`, { name }),
    deleteProject: (id) => request('DELETE', `/api/projects/${id}`),

    createClass: (projectId, name) =>
      request('POST', `/api/projects/${projectId}/classes`, { name }),
    renameClass: (id, name) => request('PATCH', `/api/classes/${id}`, { name }),
    deleteClass: (id) => request('DELETE', `/api/classes/${id}`),

    listExamples: (classId) => request('GET', `/api/classes/${classId}/examples`),
    deleteExample: (id) => request('DELETE', `/api/examples/${id}`),

    uploadExamples: (classId, files, source = 'upload') => {
      const form = new FormData();
      for (const f of files) form.append('files', f, f.name);
      form.append('source', source);
      return request('POST', `/api/classes/${classId}/examples`, form);
    },

    startTrain: (projectId, modelType, lsae) =>
      request('POST', `/api/projects/${projectId}/train`,
              { model_type: modelType, lsae }),
    trainStatus: (projectId) => request('GET', `/api/projects/${projectId}/train/status`),
    listExperiments: (projectId) => request('GET', `/api/projects/${projectId}/experiments`),
    predict: (experimentId, file) => {
      const form = new FormData();
      form.append('file', file, file.name);
      return request('POST', `/api/experiments/${experimentId}/predict`, form);
    },
    exportUrl: (experimentId) => `/api/experiments/${experimentId}/export`,

    listSigners: (projectId) => request('GET', `/api/projects/${projectId}/signers`),
    setCrossSignerSplit: (projectId, testSigner) =>
      request('POST', `/api/projects/${projectId}/cross-signer-split`, { test_signer: testSigner }),
    getCrossSignerStatus: (projectId) =>
      request('GET', `/api/projects/${projectId}/cross-signer-status`),
    listExperimentsBySigners: (projectId) =>
      request('GET', `/api/projects/${projectId}/experiments-by-signer`),

    fileUrl: (relPath) => `/files/${relPath}`,
  };
})();
