"""Create a reversible local PentAGI runtime; retain the original container.

Copies only its database setting, never cloud credentials. No engagement starts.
"""
import argparse
import json
import subprocess
from pathlib import Path


def start(image, name='kayan-pentagi-local', source='nice_brattain'):
    original = json.loads(subprocess.check_output(['docker','inspect',source]))[0]
    values = dict(item.split('=',1) for item in original['Config']['Env'])
    database = values.get('DATABASE_URL')
    if not database:
        raise RuntimeError('Original container has no DATABASE_URL; refusing to guess credentials')
    # The old container is retained for rollback. It was already stopped when
    # this helper was first used; do not interrupt it if the operator restarted it.
    if original['State']['Running']:
        raise RuntimeError('Original container is running; use a separate free host port or stop it explicitly')
    root = Path(__file__).resolve().parents[1]
    key = root/'data/roe_signing_key'
    provider_config = root/'config/pentagi_ollama.yml'
    if not key.is_file() or not provider_config.is_file():
        raise RuntimeError('Local signing key and bounded Ollama config must exist before creating the runtime')
    command = ['docker','run','-d','--name',name,'-p','127.0.0.1:8443:8080',
        '-e','DATABASE_URL='+database, '-e','SERVER_PORT=8080', '-e','SERVER_USE_SSL=false',
        '-e','EMBEDDING_PROVIDER=none', '-e','OLLAMA_SERVER_URL=http://host.docker.internal:11434',
        '-e','OLLAMA_SERVER_MODEL=qwen2.5:7b', '-e','OLLAMA_SERVER_PULL_MODELS_ENABLED=false',
        '-e','OLLAMA_SERVER_LOAD_MODELS_ENABLED=false',
        '-e','OLLAMA_SERVER_CONFIG_PATH=/run/kayan/ollama.yml',
        '-e','TRUSTGATE_BRIDGE_KEY_FILE=/run/kayan/bridge.key','-e','TRUSTGATE_URL=http://host.docker.internal:8000',
        '-e','DOCKER_IMAGE_SELECTION_MODE=fixed','-e','DOCKER_DEFAULT_IMAGE=curlimages/curl:latest',
        '-e','DOCKER_DEFAULT_IMAGE_FOR_PENTEST=curlimages/curl:latest',
        '-e','DOCKER_DEFAULT_IMAGE_FOR_TEST=curlimages/curl:latest','-e','DOCKER_ALLOWED_IMAGES=curlimages/curl:latest',
        '-e','MAX_GENERAL_AGENT_TOOL_CALLS=12','-e','MAX_LIMITED_AGENT_TOOL_CALLS=8','-e','TERMINAL_TOOL_TIMEOUT=5',
        '-v',str(key)+':/run/kayan/bridge.key:ro','-v',str(provider_config)+':/run/kayan/ollama.yml:ro',
        '-v','/var/run/docker.sock:/var/run/docker.sock', image, '/pentagi']
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    print(json.dumps({'container_id':result.stdout.strip(),'name':name,'image':image,
        'published':'127.0.0.1:8443 -> container:8080','embedding_provider':'none',
        'cloud_credentials_copied':False,'original_retained':source}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--name',default='kayan-pentagi-local')
    parser.add_argument('--source',default='nice_brattain')
    args = parser.parse_args()
    start(args.image,args.name,args.source)
