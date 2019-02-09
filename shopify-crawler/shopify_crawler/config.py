import os
import enum

class ConfigError(Exception):
    pass


class MissingKeyVaultURI(ConfigError):

    def __init__(self):
        super().__init__("Missing key vault uri")


class MissingKeyVaultSecret(ConfigError):

    def __init__(self):
        super().__init__("Missing key vault secret")



class ProjectEnv:
    DEV = 'dev'
    STAGING = 'staging'
    PRODUCTION = 'production'


def project_env():
    return os.environ.get('PROJECT_ENV', ProjectEnv.DEV)


def debug():
    return os.environ.get('DEBUG', False)


def key_vault_uri():
    try:
        return os.environ['KEY_VAULT_URI']
    except KeyError:
        raise MissingKeyVaultURI()


def key_vault_google_creds_key():
    try:
        return os.environ['KEY_VAULT_SECRET']
    except KeyError:
        raise MissingKeyVaultSecret()
