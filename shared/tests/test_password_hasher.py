from shared.auth_lib import PasswordHasher


def test_hash_verify_round_trip():
    hasher = PasswordHasher()
    h = hasher.hash('Strong-Pass-123')
    assert hasher.verify('Strong-Pass-123', h) is True
    assert hasher.verify('wrong-password', h) is False


def test_verify_garbage_hash():
    assert PasswordHasher().verify('any', 'not-a-bcrypt-hash') is False
