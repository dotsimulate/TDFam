"""
FavInstallerExt - Minimal folder-only installer for personal favorites.

This is a lightweight wrapper demonstrating the GenericInstallerEXT architecture
for a folder-only family with no embedded operators.

Users collect their favorite .tox files in a folder and they appear in the FAV menu.
"""

from installer import GenericInstallerEXT


class FavInstallerExt(GenericInstallerEXT):
    """
    FavInstallerExt - Favorites family installer.

    A minimal wrapper for folder-only operator families.
    No embedded operators - all ops come from external folder.
    """

    def __init__(self, ownerComp):
        import os
        # Get folder path - only use if it actually exists on this machine
        operators_folder = ownerComp.par.Operatorsfolder.eval()

        if not operators_folder:
            print(f"FAV Install: Warning - No Operatorsfolder specified. Menu will be empty.")
        elif not os.path.isdir(operators_folder):
            print(f"FAV Install: Warning - Operatorsfolder path does not exist: {operators_folder}")
            operators_folder = None  # Don't use stale path

        # Initialize the generic installer with FAV config
        # FAV uses dynamic_refresh=True by default so folder is scanned on each placement
        # This avoids stale cache issues when sharing the tox with different folder paths
        super().__init__(
            ownerComp=ownerComp,
            family_name=ownerComp.par.Family.eval(),
            color=ownerComp.parGroup.Color.eval(),
            compatible_types=self._get_compatible_types(ownerComp),
            operators_folder=operators_folder,
            dynamic_refresh=True,
            install_location=ownerComp.parent(),  # Stay where it is
            node_x=ownerComp.nodeX,  # Preserve current position
            node_y=ownerComp.nodeY,
            expose=True
        )

    @staticmethod
    def _get_compatible_types(ownerComp):
        """
        Get compatible types from parameter or use defaults.
        FAV family can connect to any family by default.
        """
        if hasattr(ownerComp.par, 'Compatibletypes') and ownerComp.par.Compatibletypes.eval():
            # Parse comma-separated list
            types_str = ownerComp.par.Compatibletypes.eval()
            return [t.strip() for t in types_str.split(',') if t.strip()]

        # Default: compatible with all major families
        return ['COMP', 'TOP', 'CHOP', 'SOP', 'DAT', 'MAT']

    def Install(self):
        """
        FAV-specific installation.
        Minimal - just calls parent Install.
        """
        if self.ownerComp.par.Install:
            # Re-read from parameters in case they changed since init
            self.color = self.ownerComp.parGroup.Color.eval()
            self.operators_folder = self.ownerComp.par.Operatorsfolder.eval()

            super().Install()
        else:
            super().Uninstall()

