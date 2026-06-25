from django.core.exceptions import ValidationError


class NumericPasswordValidator:
    def validate(self, password, user=None):
        if password.isdigit():
            raise ValidationError(
                "Esta contraseña es completamente numérica. Debes incluir letras o símbolos."
            )

    def get_help_text(self):
        return "Tu contraseña no puede ser completamente numérica."
