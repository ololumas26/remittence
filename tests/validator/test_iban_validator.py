from src.validator.iban_validator import (
    clean_iban,
    has_valid_format )

class TestIbanValidator:

    def test_iban_should_be_cleaned_with_blank_spaces_removed(self):
        iban = 'AO06 0006 0000 3350 3090 3011 1'
        result = clean_iban(iban)
        assert result == ''.join(iban.split(' '))

    def test_iban_should_return_an_empty_string(self):
        iban = ''
        result = clean_iban(iban)
        assert result == ''

    def test_iban_with_valid_format_return_true(self):
        iban = 'AO06 0006 0000 3350 3090 3011 1'
        result = has_valid_format(clean_iban(iban))
        assert result

    def test_iban_with_wrong_format_return_false(self):
        iban = 'AO06 0006 0000 3350 3090 3011'
        result = has_valid_format(clean_iban(iban))
        assert not result