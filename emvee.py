import sublime, sublime_plugin
import threading

def set_mode_unchecked(view, newMode):
  oldMode = get_mode(view)
  view.settings().set('emvee_mode', newMode)
  if oldMode == 'select' and newMode == 'normal':
    view.run_command('emvee_clear_selection')

def set_mode(view, newMode):
  if newMode not in get_available_modes():
    print("Unknown mode:", newMode)
    return False
  set_mode_unchecked(view, newMode)
  return True

def get_available_modes():
  return ('normal', 'select')

def get_mode(view):
  if not view.settings().has('emvee_mode'):
    view.settings().set('emvee_mode', 'normal')
  mode = view.settings().get('emvee_mode')
  return mode

def get_next_mode(mode, *, steps=1, modes=None):
  '''Allows negative number of steps'''
  if modes is None or len(modes) == 0:
    modes = get_available_modes()

  if mode not in modes:
    return modes[0]

  currentIndex = modes.index(mode)
  nextIndex = currentIndex + steps
  # Wrap around.
  nextIndex = nextIndex % len(modes)
  return modes[nextIndex]

def has_non_empty_selection(view):
  # Check for any non-empty selections and force extending all if one is
  # found.
  for region in view.sel():
    if region.a != region.b:
      return True

  return False


class EmveeEventListener(sublime_plugin.EventListener):
  def on_load(self, view):
    set_mode(view, 'normal')
    
  def on_query_context(self, view, key, operator, operand, match_all):
    if key == 'emvee_early_out':
      return False

    if key == 'emvee_mode':
      if operator == sublime.OP_EQUAL:     return operand == get_mode(view)
      if operator == sublime.OP_NOT_EQUAL: return operand != get_mode(view)
    elif key == 'emvee_force_set_mode':
      return set_mode(view, operand)
    elif key == 'emvee_force_next_mode':
      oldMode = get_mode(view)
      newMode = get_next_mode(oldMode, steps=1, modes=operand)
      return set_mode(view, newMode)


class EmveeCommand(sublime_plugin.TextCommand):
  def run(self, edit):
    print("Emvee: Help is coming soon.")


class EmveeNextModeCommand(sublime_plugin.TextCommand):
  def run(self, edit, *, delta):
    delta = int(delta)
    oldMode = get_mode(self.view)
    newMode = get_next_mode(oldMode, steps=delta)
    set_mode(self.view, newMode)


class EmveeSetModeCommand(sublime_plugin.TextCommand):
  def run(self, edit, *, mode):
    return set_mode(self.view, mode)


class EmveeClearSelectionCommand(sublime_plugin.TextCommand):
  def run(self, edit):
    selection = list(self.view.sel())
    self.view.sel().clear()

    # Flatten the existing selections.
    for index in range(len(selection)):
      region = selection[index]
      region.a = region.b
      selection[index] = region
    self.view.sel().add_all(selection)


class EmveeMoveCommand(sublime_plugin.TextCommand):
  def run(self, edit, *, delta=0, by=None, extend=False):
    supportedArgsForBy = ('char', 'lines', 'word_begin', 'word_end', 'subword', 'line_limit', 'empty_line')
    if by not in supportedArgsForBy:
      raise ValueError('Don\'t know "{}". Supported arguments for "by": {}'.format(by, supportedArgsForBy))

    if delta == 0:
      return

    forceExtend = extend
    if not forceExtend:
      forceExtend = has_non_empty_selection(self.view)

    if forceExtend and get_mode(self.view) != 'select':
      set_mode(self.view, 'select')

    amount = abs(delta)
    forward = delta > 0
    args = {
      'forward': forward,
      'extend': get_mode(self.view) == 'select'
    }

    # 
    # By char
    # 
    if by == 'char':
      args['by'] = 'characters';
      for _ in range(amount):
        self.view.run_command('move', args)


    # 
    # By lines
    # 
    elif by == 'lines':
      args['by'] = 'lines';
      for _ in range(amount):
        self.view.run_command('move', args)

    # 
    # By word
    # 
    elif by in ('word_begin', 'word_end'):
      args['by'] = 'words' if by == 'word_begin' else 'word_ends';
      for _ in range(amount):
        self.view.run_command('move', args)

    # 
    # By subword
    # 
    elif by == 'subword':
      args['by'] = 'subwords';
      for _ in range(amount):
        self.view.run_command('move', args)

    # 
    # By line_limit
    # 
    elif by == 'line_limit':
      args['to'] = 'eol' if forward else 'bol'
      self.view.run_command('move_to', args)

    # 
    # By empty_line
    # 
    elif by == 'empty_line':
      selection = list(self.view.sel())
      self.view.sel().clear()
      region = selection[0] if len(selection) > 0 else sublime.Region(0, 0)
      for _ in range(amount):
        region = self.view.find_by_class(region.b, forward, sublime.CLASS_EMPTY_LINE)
      self.view.sel().add(region)
      self.view.show(self.view.sel(), True)

    # 
    # Unhandled cases
    # 
    else:
      assert False, 'Unhandled "by": {}'.format(by)


class EmveeScrollCommand(sublime_plugin.TextCommand):
  def run(self, edit, *, lines=0, screensX=0, screensY=0, centerCursor=False):
    lines = float(lines)
    screensY = float(screensY)
    screensX = float(screensX)

    if screensY:
      extent = self.view.viewport_extent()
      linesPerScreen = extent[1] / self.view.line_height()
      lines += screensY * linesPerScreen

    if lines:
      self.view.run_command('scroll_lines', { 'amount': lines })

    if screensX:
      position = self.view.viewport_position()
      extent = self.view.viewport_extent()
      maxExtent = self.view.layout_extent()
      maxX = maxExtent[0] - extent[0]
      if maxX > 0:
        offsetX = screensX * extent[0]
        newX = position[0] + offsetX
        newX = max(0, min(newX, maxX))
        newPosition = (newX, position[1])
        self.view.set_viewport_position(newPosition)

    if centerCursor:
      selection = self.view.sel()
      if len(selection) > 1:
        self.view.show(self.view.sel(), True)
      else:
        extent = self.view.show_at_center(selection[0])


class EmveeDeleteCommand(sublime_plugin.TextCommand):
  def run(self, edit, *, delta=0, by):
    supportedArgsForBy = ('char', 'word', 'line_from_cursor', 'line', 'full_line')
    if by not in supportedArgsForBy:
      raise ValueError('Don\'t know "{}". Supported arguments for "by": {}'.format(by, supportedArgsForBy))

    delta = int(delta)
    if delta == 0:
      return

    forward = delta > 0
    amount = abs(delta)

    # 
    # By char
    # 
    if by == 'char':
      command = 'right_delete' if forward else 'left_delete'

      self.view.run_command('add_to_kill_ring', { 'forward': forward })
      for _ in range(amount):
        self.view.run_command(command)

    # 
    # By word
    # 
    elif by == 'word':
      for _ in range(amount):
        self.view.run_command('delete_word', { 'forward': forward })

    # 
    # By line relative to the cursor
    # 
    elif by in ('line_from_cursor', 'full_line_from_cursor'):
      command = 'right_delete' if forward else 'left_delete'
      selection = list(self.view.sel())
      self.view.sel().clear()
      func = getattr(self.view, 'line' if by == 'line_from_cursor' else 'full_line')
      for index in range(len(selection)):
        region = selection[index]
        row, _ = self.view.rowcol(region.end())
        line = func(self.view.text_point(row + amount - 1, 0))
        if forward:
          region = sublime.Region(region.begin(), line.end())
        else:
          region = sublime.Region(line.begin(), region.end())
        selection[index] = region
      self.view.sel().add_all(selection)
      self.view.run_command('add_to_kill_ring', { 'forward': forward })
      self.view.run_command(command)

    # 
    # By line
    # 
    elif by in ('line', 'full_line'):
      if forward:
        for _ in range(amount):
          selection = list(self.view.sel())
          self.view.sel().clear()
          func = getattr(self.view, by)
          for index in range(len(selection)):
            selection[index] = func(selection[index])
          self.view.sel().add_all(selection)
          self.view.run_command('add_to_kill_ring', { 'forward': forward })
        self.view.run_command('right_delete')
      else:
        print('line operations only support positive deltas.')

    if get_mode(self.view) == 'select':
      set_mode(self.view, 'normal')


class EmveeSwapLinesCommand(sublime_plugin.TextCommand):
  def run(self, edit, *, delta=0):
    while delta > 0:
      delta -= 1
      self.view.run_command('swap_line_down')
    while delta < 0:
      delta += 1
      self.view.run_command('swap_line_up')


class EmveeSwapCursorWithAnchorCommand(sublime_plugin.TextCommand):
  def run(self, edit, *, side):
    supportedSides = ('toggle', 'begin', 'end', )
    if side not in supportedSides:
      raise ValueError('Don\'t know "{}". Supported arguments for "side": {}'.format(side, supportedSides))

    selection = list(self.view.sel())
    self.view.sel().clear()

    if side == 'toggle':
      selection = [sublime.Region(reg.b, reg.a) for reg in selection]
    elif side == 'begin':
      selection = [sublime.Region(reg.end(), reg.begin()) for reg in selection]
    elif side == 'end':
      selection = [sublime.Region(reg.begin(), reg.end()) for reg in selection]

    self.view.sel().add_all(selection)

