# DATExecute callback for config tables
# Monitor: group_mapping, replace_index, os_incompatible, relabel_index, settings
#
# This callback syncs DAT table changes to the Config DependDict.
# The ConfigManager._syncing flag prevents infinite loops when
# syncing from Config to tables.

def onTableChange(dat):
    installer = parent()
    if hasattr(installer, 'config') and installer.config:
        installer.config.on_table_change(dat.name)

def onRowChange(dat, rows, cols):
    onTableChange(dat)

def onColChange(dat, cols):
    onTableChange(dat)

def onCellChange(dat, cells, prev):
    onTableChange(dat)

def onSizeChange(dat):
    onTableChange(dat)
