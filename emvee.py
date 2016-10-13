import sublime, sublime_plugin
import threading

actionLookup_Class2Name = {}
actionLookup_Name2Class = {}

def emvee_action(actionName):
  '''Note: This is a decorator.'''
  def helper(actionClass):
    actionLookup_Name2Class[actionName] = actionClass
    actionLookup_Class2Name[actionClass] = actionName
    return actionClass
  return helper


def set_mode_unchecked(view, newMode):
  oldMode = get_mode(view)
  # print(oldMode, "=>", newMode)
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

def run_emvee_action(view, actionClass, **kwargs):
  kwargs['action'] = actionLookup_Class2Name[actionClass]
  view.run_command('emvee', kwargs)


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
  def run(self, edit, *, action, **kwargs):
    '''Internal dispatch'''
    try:
      actionClass = actionLookup_Name2Class[action]
    except KeyError:
      print('No such emvee action:', action, file=sys.stderr)
      return
    actionInstance = actionClass()
    actionInstance.run(self, edit, **kwargs)


class EmveeAction:
  """Base class for emvee actions."""
  pass


@emvee_action("next_mode")
class NextMode(EmveeAction):
  def run(self, subl, edit, *, delta):
    delta = int(delta)
    oldMode = get_mode(subl.view)
    newMode = get_next_mode(oldMode, steps=delta)
    set_mode(subl.view, newMode)
    if oldMode == 'select':
      run_emvee_action(subl.view, ClearSelection)
      subl.view.run_command('emvee', { 'action': 'clear_selection' })


@emvee_action("set_mode")
class SetMode(EmveeAction):
  def run(self, subl, edit, *, mode):
    return set_mode(subl.view, mode)


@emvee_action("clear_selection")
class ClearSelection(EmveeAction):
  def run(self, subl, edit):
    selection = list(subl.view.sel())
    subl.view.sel().clear()

    # Flatten the existing selections.
    for index in range(len(selection)):
      region = selection[index]
      region.a = region.b
      selection[index] = region
    subl.view.sel().add_all(selection)


@emvee_action("move")
class Move(EmveeAction):
  def run(self, subl, edit, *, delta=0, by=None, extend=False):
    supportedArgsForBy = ('char', 'lines', 'word_begin', 'word_end', 'subword', 'line_limit', 'empty_line')
    if by not in supportedArgsForBy:
      raise ValueError('Don\'t know "{}". Supported arguments for "by": {}'.format(by, supportedArgsForBy))

    if delta == 0:
      return

    forceExtend = extend
    if not forceExtend:
      forceExtend = has_non_empty_selection(subl.view)

    if forceExtend and get_mode(subl.view) != 'select':
      set_mode(subl.view, 'select')

    amount = abs(delta)
    forward = delta > 0
    extend = get_mode(subl.view) == 'select'
    args = {
      'forward': forward,
      'extend': extend
    }

    #
    # By char
    #
    if by == 'char':
      args['by'] = 'characters';
      for _ in range(amount):
        subl.view.run_command('move', args)


    #
    # By lines
    #
    elif by == 'lines':
      args['by'] = 'lines';
      for _ in range(amount):
        subl.view.run_command('move', args)

    #
    # By word
    #
    elif by in ('word_begin', 'word_end'):
      args['by'] = 'words' if by == 'word_begin' else 'word_ends';
      for _ in range(amount):
        subl.view.run_command('move', args)

    #
    # By subword
    #
    elif by == 'subword':
      args['by'] = 'subwords';
      for _ in range(amount):
        subl.view.run_command('move', args)

    #
    # By line_limit
    #
    elif by == 'line_limit':
      args['to'] = 'eol' if forward else 'bol'
      subl.view.run_command('move_to', args)

    #
    # By empty_line
    #
    elif by == 'empty_line':
      selection = list(subl.view.sel())
      subl.view.sel().clear()
      region = selection[0] if len(selection) > 0 else sublime.Region(0, 0)
      for _ in range(amount):
        region.b = subl.view.find_by_class(region.b, forward, sublime.CLASS_EMPTY_LINE)

      if not extend:
        region.a = region.b

      subl.view.sel().add(region)
      subl.view.show(subl.view.sel(), True)

    #
    # Unhandled cases
    #
    else:
      assert False, 'Unhandled "by": {}'.format(by)


@emvee_action("scroll")
class Scroll(EmveeAction):
  def run(self, subl, edit, *, lines=0, screensX=0, screensY=0, centerCursor=False):
    lines = float(lines)
    screensY = float(screensY)
    screensX = float(screensX)

    if screensY:
      extent = subl.view.viewport_extent()
      linesPerScreen = extent[1] / subl.view.line_height()
      lines += screensY * linesPerScreen

    if lines:
      subl.view.run_command('scroll_lines', { 'amount': lines })

    if screensX:
      position = subl.view.viewport_position()
      extent = subl.view.viewport_extent()
      maxExtent = subl.view.layout_extent()
      maxX = maxExtent[0] - extent[0]
      if maxX > 0:
        offsetX = screensX * extent[0]
        newX = position[0] + offsetX
        newX = max(0, min(newX, maxX))
        newPosition = (newX, position[1])
        subl.view.set_viewport_position(newPosition)

    if centerCursor:
      selection = subl.view.sel()
      if len(selection) > 1:
        subl.view.show(subl.view.sel(), True)
      else:
        extent = subl.view.show_at_center(selection[0])


@emvee_action("delete")
class Delete(EmveeAction):
  def run(self, subl, edit, *, delta, by):
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
      sublCommand = 'right_delete' if forward else 'left_delete'

      subl.view.run_command('add_to_kill_ring', { 'forward': forward })
      for _ in range(amount):
        subl.view.run_command(sublCommand)

    #
    # By word
    #
    elif by == 'word':
      for _ in range(amount):
        subl.view.run_command('delete_word', { 'forward': forward })

    #
    # By line relative to the cursor
    #
    elif by in ('line_from_cursor', 'full_line_from_cursor'):
      sublCommand = 'right_delete' if forward else 'left_delete'
      selection = list(subl.view.sel())
      subl.view.sel().clear()
      func = getattr(subl.view, 'line' if by == 'line_from_cursor' else 'full_line')
      for index in range(len(selection)):
        region = selection[index]
        row, _ = subl.view.rowcol(region.end())
        line = func(subl.view.text_point(row + amount - 1, 0))
        if forward:
          region = sublime.Region(region.begin(), line.end())
        else:
          region = sublime.Region(line.begin(), region.end())
        selection[index] = region
      subl.view.sel().add_all(selection)
      subl.view.run_command('add_to_kill_ring', { 'forward': forward })
      subl.view.run_command(sublCommand)

    #
    # By line
    #
    elif by in ('line', 'full_line'):
      if forward:
        for _ in range(amount):
          selection = list(subl.view.sel())
          subl.view.sel().clear()
          func = getattr(subl.view, by)
          for index in range(len(selection)):
            selection[index] = func(selection[index])
          subl.view.sel().add_all(selection)
          subl.view.run_command('add_to_kill_ring', { 'forward': forward })
        subl.view.run_command('right_delete')
      else:
        print('line operations only support positive deltas.')

    if get_mode(subl.view) == 'select':
      set_mode(subl.view, 'normal')


@emvee_action("swap_lines")
class SwapLines(EmveeAction):
  def run(self, subl, edit, *, delta=0):
    while delta > 0:
      delta -= 1
      subl.view.run_command('swap_line_down')
    while delta < 0:
      delta += 1
      subl.view.run_command('swap_line_up')


@emvee_action("swap_cursor_with_anchor")
class SwapCursorWithAnchor(EmveeAction):
  def run(self, subl, edit, *, side):
    supportedSides = ('toggle', 'begin', 'end', )
    if side not in supportedSides:
      raise ValueError('Don\'t know "{}". Supported arguments for "side": {}'.format(side, supportedSides))

    selection = list(subl.view.sel())
    subl.view.sel().clear()

    if side == 'toggle':
      selection = [sublime.Region(reg.b, reg.a) for reg in selection]
    elif side == 'begin':
      selection = [sublime.Region(reg.end(), reg.begin()) for reg in selection]
    elif side == 'end':
      selection = [sublime.Region(reg.begin(), reg.end()) for reg in selection]

    subl.view.sel().add_all(selection)

