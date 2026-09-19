BCRYPT_MAX_PASSWORD_BYTES = 72


def validate_password_length(plain_password: str) -> str:
    if plain_password is None:
        raise ValueError("Password cannot be longer than 72 bytes.")
    if len(plain_password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError("Password cannot be longer than 72 bytes.")
    return plain_password
