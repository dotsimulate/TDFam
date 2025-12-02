# me - this DAT.
# 
# dat - the changed DAT
# rows - a list of row indices
# cols - a list of column indices
# prev - the list of previous string contents of the changed cells
# 
# Make sure the corresponding toggle is enabled in the DAT Execute DAT.
# 
# If rows or columns are deleted, sizeChange will be called instead of row/col/cellChange.


def onTableChange(dat):
    installer = parent()
    if hasattr(installer, 'config') and installer.config:
        installer.config.on_table_change(dat.name)

def onRowChange(dat, rows):
	return

def onColChange(dat, cols):
	return

def onCellChange(dat, cells, prev):
	return

def onSizeChange(dat):
	return
	