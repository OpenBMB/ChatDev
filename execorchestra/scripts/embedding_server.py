"""Local, authenticated embedding endpoint. Model loading occurs only at startup."""
from contextlib import asynccontextmanager
import hmac
import os
from pathlib import Path
import threading

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

MODEL_ID = 'sgar-embedding-4b'
REVISION = '5cf2132abc99cad020ac570b19d031efec650f2b'
DIMENSION = 2560
MAX_TOKENS = 32768
ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(os.environ.get('SGAR_EMBEDDING_MODEL_PATH', str(ROOT / '.cache/embedding-model')))
state = {}
lock = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    if not os.environ.get('SLURM_JOB_ID') and os.environ.get('SGAR_EMBEDDING_DEDICATED_GPU') != '1':
        raise RuntimeError('Use an active Slurm GPU allocation or explicitly set SGAR_EMBEDDING_DEDICATED_GPU=1 on a dedicated GPU server')
    if not os.environ.get('SGAR_EMBEDDING_API_KEY'):
        raise RuntimeError('SGAR_EMBEDDING_API_KEY is required')
    import torch
    from transformers import AutoModel, AutoTokenizer
    if not torch.cuda.is_available():
        raise RuntimeError('No allocated CUDA GPU is visible')
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('The allocated GPU does not support BF16')
    tokenizer = AutoTokenizer.from_pretrained(
        str(MODEL_PATH), local_files_only=True, trust_remote_code=False,
        padding_side='left')
    model = AutoModel.from_pretrained(
        str(MODEL_PATH), local_files_only=True, trust_remote_code=False,
        dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    if model.config.hidden_size != DIMENSION:
        raise RuntimeError('Unexpected embedding dimension')
    state.update(model=model, tokenizer=tokenizer)
    try:
        yield
    finally:
        state.clear()
        del model
        torch.cuda.empty_cache()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: str
    input: str | list[str]
    encoding_format: str = 'float'
    dimensions: int = Field(default=DIMENSION)


@app.get('/healthz')
def health():
    if 'model' not in state:
        raise HTTPException(503, 'Model is not ready')
    return {'ready': True, 'model': MODEL_ID, 'revision': REVISION, 'dimensions': DIMENSION}


@app.post('/v1/embeddings')
def embeddings(body: EmbeddingRequest, authorization: str = Header(default='')):
    key = os.environ.get('SGAR_EMBEDDING_API_KEY', '')
    if not key or not hmac.compare_digest(authorization, 'Bearer ' + key):
        raise HTTPException(401, 'Invalid API key')
    if body.model != MODEL_ID:
        raise HTTPException(400, 'Unsupported model')
    if body.dimensions != DIMENSION or body.encoding_format != 'float':
        raise HTTPException(400, 'Only 2560-dimensional float embeddings are supported')
    inputs = [body.input] if isinstance(body.input, str) else body.input
    if not inputs or len(inputs) > 64:
        raise HTTPException(400, 'Provide between 1 and 64 input strings')
    if sum(len(s) for s in inputs) > 8 * 1024 * 1024:
        raise HTTPException(413, 'Input is too large')
    import torch
    import torch.nn.functional as functional
    with lock, torch.inference_mode():
        tokenizer, model = state['tokenizer'], state['model']
        tokens = tokenizer(inputs, padding=False, truncation=False)
        counts = [len(ids) for ids in tokens['input_ids']]
        if any(n == 0 or n > MAX_TOKENS for n in counts):
            raise HTTPException(400, 'Each input must contain 1 to 32768 tokens; no silent truncation')
        results = []
        # Fixed microbatch of one keeps 32K requests within a bounded memory footprint.
        # The caller already adds query instructions; do not add a second prefix here.
        try:
            for i in range(len(inputs)):
                batch = {k: torch.tensor([v[i]], device='cuda') for k, v in tokens.items()}
                hidden = model(**batch).last_hidden_state
                vector = functional.normalize(hidden[:, -1, :].float(), p=2, dim=1)
                if not torch.isfinite(vector).all():
                    raise HTTPException(500, 'Non-finite embedding')
                results.append({'object': 'embedding', 'index': i,
                                'embedding': vector[0].cpu().tolist()})
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            raise HTTPException(503, 'GPU memory exhausted; reduce input length') from None
    total = sum(counts)
    return {'object': 'list', 'data': results, 'model': MODEL_ID,
            'usage': {'prompt_tokens': total, 'total_tokens': total}}


if __name__ == '__main__':
    if not os.environ.get('SLURM_JOB_ID') and os.environ.get('SGAR_EMBEDDING_DEDICATED_GPU') != '1':
        raise SystemExit('Use a Slurm allocation or explicitly select a dedicated GPU server')
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8001, workers=1, access_log=False)
