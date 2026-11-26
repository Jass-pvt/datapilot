import pytest

from lab.users.importer import RowError, validate_email, validate_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Ada   Lovelace ", "Ada Lovelace"),
        ("José Álvarez", "José Álvarez"),
        ("Anne-Marie O'Neil", "Anne-Marie O'Neil"),
        ("J. R. Tolkien", "J. R. Tolkien"),
    ],
)
def test_valid_names(raw, expected):
    assert validate_name(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "1234",
        "Robert'); DROP TABLE users;--",
        "=cmd|' /C calc'!A0",
        "x" * 101,
        "<script>alert(1)</script>",
    ],
)
def test_invalid_names(raw):
    with pytest.raises(RowError):
        validate_name(raw)


def test_valid_email_is_lowercased_and_trimmed():
    assert validate_email("  Bob@Example.COM ") == "bob@example.com"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "plain",
        "a@b",
        "a@@b.com",
        "a b@c.com",
        "a..b@c.com",
        "@c.com",
        "a@-c.com",
        "a@c.com\nBcc: x@y.com",
        ("a" * 250) + "@c.com",
        "o'brien@x.com' OR '1'='1",
    ],
)
def test_invalid_emails(raw):
    with pytest.raises(RowError):
        validate_email(raw)
