"""
File-based operator loading for opfam-create.

Handles loading operators from external .tox files, with caching and
version comparison against embedded operators.
"""

import os
import re


class FileLoader:
    """
    Manages loading operators from external .tox files.

    Supports:
    - Folder scanning and caching
    - Version parsing from filenames
    - Resolution between embedded and file-based operators
    """

    def __init__(self, installer):
        """
        Initialize the file loader.

        Args:
            installer: The OpFamCreateExt instance
        """
        self.installer = installer
        self.ownerComp = installer.ownerComp
        self.family_name = installer.FamilyName.val

        # Folder cache as tdu.Dependency for reactive updates
        self.cache = tdu.Dependency({})

    def refresh_cache(self, operators_folder):
        """
        Scan external folder and build cache of available operators.

        Args:
            operators_folder: Path to folder containing .tox files

        Cache structure: {name: {'path': str, 'version': str|None, 'category': str|None}}
        """
        new_cache = {}

        if not operators_folder or not os.path.isdir(operators_folder):
            self.cache.val = new_cache
            return

        for item in os.listdir(operators_folder):
            item_path = os.path.join(operators_folder, item)

            if os.path.isdir(item_path):
                # Subfolder = category
                category_name = item
                for f in os.listdir(item_path):
                    if f.endswith('.tox'):
                        name, version = self._parse_tox_info(f)
                        if name:
                            new_cache[name.lower()] = {
                                'path': os.path.join(item_path, f),
                                'version': version,
                                'category': category_name
                            }

            elif item.endswith('.tox'):
                # Loose file = no category
                name, version = self._parse_tox_info(item)
                if name:
                    new_cache[name.lower()] = {
                        'path': os.path.join(operators_folder, item),
                        'version': version,
                        'category': None
                    }

        print(f"{self.family_name}: Folder cache refreshed - {len(new_cache)} operators found")
        self.cache.val = new_cache

    def _parse_tox_info(self, filename):
        """
        Parse operator name and version from .tox filename.

        Supports patterns:
        - name_vX.Y.Z.tox -> (name, "X.Y.Z")
        - name.tox -> (name, None)

        Args:
            filename: The .tox filename

        Returns:
            tuple: (name, version) or (None, None) if invalid
        """
        match = re.match(r'(.+)_v(\d+\.\d+\.\d+)\.tox$', filename)
        if match:
            return (match.group(1), match.group(2))

        if filename.endswith('.tox'):
            return (filename[:-4], None)

        return (None, None)

    def _parse_version(self, ver_string):
        """
        Parse version string to tuple for comparison.

        Args:
            ver_string: Version string like "1.2.3"

        Returns:
            tuple: (1, 2, 3) or None if invalid
        """
        if not ver_string:
            return None
        try:
            return tuple(int(x) for x in ver_string.split('.'))
        except:
            return None

    def get_operator_source(self, lookup_name, operators_folder=None, dynamic_refresh=False):
        """
        Get operator source - embedded or file-based.

        Resolution logic:
        1. Match in BOTH, external has NO version -> Use EMBEDDED (authoritative)
        2. Match in BOTH, external HAS version -> VERSION COMPARE, higher wins
        3. Only in EMBEDDED -> Use EMBEDDED
        4. Only in FOLDER -> Use FOLDER

        Args:
            lookup_name: Operator name to find (lowercase)
            operators_folder: Path to external folder (for dynamic refresh)
            dynamic_refresh: If True, scan folder live instead of using cache

        Returns:
            tuple: ('embedded', op) or ('file', path) or None
        """
        # Find embedded operator from operators_comp
        custom_ops = self.installer.operators_comp
        embedded_ops = custom_ops.findChildren(name=lookup_name, maxDepth=1) if custom_ops else []
        embedded = embedded_ops[0] if embedded_ops else None

        # Find external .tox
        external_info = None
        if dynamic_refresh and operators_folder:
            # Live scan
            if os.path.isdir(operators_folder):
                for f in os.listdir(operators_folder):
                    if not f.endswith('.tox'):
                        continue
                    name, version = self._parse_tox_info(f)
                    if name and name.lower() == lookup_name:
                        external_info = {
                            'path': os.path.join(operators_folder, f),
                            'version': version
                        }
                        break
        else:
            # Use cache
            folder_cache = self.cache.val
            if folder_cache:
                external_info = folder_cache.get(lookup_name)

        # Resolution logic
        if external_info and not embedded:
            return ('file', external_info['path'])

        if embedded and not external_info:
            return ('embedded', embedded)

        if not embedded and not external_info:
            return None

        # Both exist - check versioning
        external_version = external_info.get('version') if external_info else None

        if external_version is None:
            # External has no version -> embedded wins
            return ('embedded', embedded)

        # External has version - compare
        embedded_version = None
        if hasattr(embedded.par, 'Version'):
            embedded_version = self._parse_version(str(embedded.par.Version.eval()))

        external_ver_tuple = self._parse_version(external_version)

        if embedded_version is None:
            # Embedded unversioned, external versioned -> use external
            return ('file', external_info['path'])

        # Both versioned - higher wins, tie goes to embedded
        if external_ver_tuple and external_ver_tuple > embedded_version:
            return ('file', external_info['path'])

        return ('embedded', embedded)

    def get_master_for_type(self, op_type, target_parent, operators_folder=None, dynamic_refresh=False):
        """
        Get master operator for a type, checking both embedded and external folder.

        Args:
            op_type: The operator type name to find
            target_parent: Parent to load file-based operators into
            operators_folder: Path to external folder
            dynamic_refresh: Whether to scan folder live

        Returns:
            tuple: (master_op, is_file_based) or (None, False) if not found
        """
        source_result = self.get_operator_source(op_type, operators_folder, dynamic_refresh)

        if source_result is None:
            return (None, False)

        if source_result[0] == 'embedded':
            return (source_result[1], False)

        if source_result[0] == 'file':
            try:
                loaded = target_parent.loadTox(source_result[1])
                return (loaded, True)
            except Exception as e:
                print(f"Error loading master from file {source_result[1]}: {e}")
                return (None, False)

        return (None, False)
