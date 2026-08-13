__all__ = [
    "launch_app",
    "AppGestionLoyers",
    "LoginDialog",
    "FormulaireSouscription",
    "NouveauSouscripteurDialog",
    "ExportPDFDialog",
]


def __getattr__(name):
    """Charge les composants UI uniquement lorsqu'ils sont réellement utilisés."""
    if name == "launch_app":
        from tap.presentation.bootstrap import launch_app
        return launch_app
    if name == "AppGestionLoyers":
        from tap.presentation.views.main_window import AppGestionLoyers
        return AppGestionLoyers
    if name == "LoginDialog":
        from tap.presentation.dialogs.login import LoginDialog
        return LoginDialog
    if name in {"FormulaireSouscription", "NouveauSouscripteurDialog"}:
        from tap.presentation.dialogs.formulaire import (
            FormulaireSouscription,
            NouveauSouscripteurDialog,
        )
        return locals()[name]
    if name == "ExportPDFDialog":
        from tap.presentation.dialogs.export_pdf import ExportPDFDialog
        return ExportPDFDialog
    raise AttributeError(name)
