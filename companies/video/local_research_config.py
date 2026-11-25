"""Local dotenv loading and read-only research readiness checks."""
import os
import re
import shlex

from autonomous_company import CompanyError
from autonomous_gemini35 import ENDPOINT, MODEL, Gemini35Config
from mission_production import production_keys

VARIABLES = frozenset(('GEMINI_API_KEY', 'GEMINI_PRODUCTION_PROJECT_API_KEY', 'GEMINI35_MODEL',
                       'GEMINI35_ENDPOINT', 'GEMINI35_AUTONOMOUS_FREE_ENABLED',
                       'GROQ_API_KEY', 'TAVILY_API_KEY', 'TAVILY_RESEARCHER_FREE_ONLY', 'YOUTUBE_DATA_API_KEY'))


def load_environment(path):
    pending = {}
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        raise CompanyError('local_env_unreadable') from None
    for index, raw in enumerate(lines, 1):
        line = raw.strip().removeprefix('export ').lstrip()
        name, separator, value = line.partition('=')
        if name.strip() not in VARIABLES:
            continue
        try:
            parts = shlex.split(value, comments=True)
        except ValueError:
            parts = ['', '']
        if not separator or len(parts) > 1 or name.strip() in pending:
            raise CompanyError(f'local_env_invalid_line_{index}')
        pending[name.strip()] = parts[0] if parts else ''
    for name, value in pending.items():
        os.environ.setdefault(name, value)
    os.environ.setdefault('GEMINI35_MODEL', MODEL)
    os.environ.setdefault('GEMINI35_ENDPOINT', ENDPOINT)


def readiness():
    config = Gemini35Config.from_env()
    blockers = []
    if (config.model, config.endpoint) != (MODEL, ENDPOINT):
        blockers.append('gemini_model_or_endpoint_mismatch')
    if os.getenv('GEMINI35_AUTONOMOUS_FREE_ENABLED') != '1':
        blockers.append('gemini_free_execution_disabled')
    if not os.getenv('GEMINI_API_KEY'):
        blockers.append('gemini_key_missing')
    if not os.getenv('GEMINI_PRODUCTION_PROJECT_API_KEY'):
        blockers.append('independent_production_key_missing')
    elif os.getenv('GEMINI_API_KEY'):
        try:
            production_keys()
        except CompanyError:
            blockers.append('production_project_key_mismatch')
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,200}',os.getenv('TAVILY_API_KEY','')):
        blockers.append('tavily_key_missing_or_invalid')
    if os.getenv('TAVILY_RESEARCHER_FREE_ONLY') != '1':
        blockers.append('tavily_free_only_disabled')
    return dict(configuration='blocked' if blockers else 'configured', configuration_blockers=blockers,
                provider_account_condition='unverified_locally', provider_billing='unknown',
                provider_quota='unknown', execution='separate_signed_approval_required')
