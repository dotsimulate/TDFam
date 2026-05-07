# me is this DAT.
#
# dat is the DAT that recieved the key event.
# key is the name of the key attached to the event
# character is the ASCII value of the pressed key as a string
# alt is true if the alt modifier is pressed
# ctrl is true if the ctrl modifier is pressed
# shift is true if the shift modifier is pressed
# state is true if the event is a key press event
# time is the time when the event came in milliseconds


def keyEvent(dat, key, character, alt, lAlt, rAlt, ctrl, lCtrl, rCtrl, shift, lShift, rShift, state, time):
	return

def shortcutEvent(dat, shortcutName, time):
	owner = dat.parent()
	if not owner.isOpen:
		return

	import td
	numCols = owner.op('families/family').par.tablecols.eval()
	numRows = owner.op('families/family').par.tablerows.eval()
	n = len(td.families) + len(op.FAMREGISTRY.InstalledFams) + 1

	current = int(owner.op('families/out1')['cellradioid'][0])
	cur_row = current // numCols
	cur_col = current % numCols

	def go(r, c):
		idx = r * numCols + c
		if 0 <= idx < n:
			owner.op('families/family').click(r, c)

	if shortcutName in ('tab', 'right'):
		next_idx = (current + 1) % n
		go(next_idx // numCols, next_idx % numCols)

	elif shortcutName in ('shift.tab', 'left'):
		next_idx = (current - 1) % n
		go(next_idx // numCols, next_idx % numCols)

	elif shortcutName == 'down':
		next_row = (cur_row + 1) % numRows
		if next_row * numCols + cur_col >= n:
			go(next_row, 0)
		else:
			go(next_row, cur_col)

	elif shortcutName == 'up':
		next_row = (cur_row - 1) % numRows
		if next_row * numCols + cur_col >= n:
			go(next_row, (n - 1) % numCols)
		else:
			go(next_row, cur_col)

	return
