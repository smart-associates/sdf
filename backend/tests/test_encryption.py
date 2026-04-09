import pytest
from app.services.encryption import encrypt, decrypt, mask, is_masked, MASKED, DecryptionError


def test_encrypt_decrypt_roundtrip():
    plaintext = "my-secret-password"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext


def test_encrypt_empty_string_passthrough():
    assert encrypt("") == ""
    assert decrypt("") == ""


def test_decrypt_invalid_ciphertext_raises():
    with pytest.raises(DecryptionError):
        decrypt("not-a-valid-ciphertext")


def test_mask_returns_masked():
    assert mask("anything") == MASKED
    assert mask("") == ""


def test_is_masked():
    assert is_masked(MASKED) is True
    assert is_masked("something-else") is False
