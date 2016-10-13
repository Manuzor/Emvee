import sublime, sublime_plugin
import threading
import sys
import difflib

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

globalDigitPrefix = None

class EmveeCommand(sublime_plugin.TextCommand):
  def run(self, edit, *, action, **kwargs):
    '''Internal dispatch'''
    try:
      actionClass = actionLookup_Name2Class[action]
    except KeyError:
      print('No such emvee action:', action, file=sys.stderr)
      threshold = 0.6
      matches = []
      for name in actionLookup_Name2Class:
        if difflib.SequenceMatcher(None, action, name).ratio() > threshold:
          matches.append(name)
      if matches:
        print('Did you mean:', *matches, sep='\n  ', file=sys.stderr)
      return

    amount = 1
    if globalDigitPrefix is not None:
      amount = int(globalDigitPrefix)

    actionInstance = actionClass(amount, **kwargs)
    actionInstance.run(self, edit)


class EmveeAction:
  """Base class for emvee actions."""
  pass

@emvee_action("next_mode")
class NextMode(EmveeAction):
  def __init__(self, amount):
    self.delta = amount

  def run(self, subl, edit):
    oldMode = get_mode(subl.view)
    newMode = get_next_mode(oldMode, steps=self.delta)
    set_mode(subl.view, newMode)
    if oldMode == 'select':
      run_emvee_action(subl.view, ClearSelection)
      subl.view.run_command('emvee', { 'action': 'clear_selection' })


@emvee_action("set_mode")
class SetMode(EmveeAction):
  def __init__(self, amount, *, mode):
    self.mode = mode

  def run(self, subl, edit):
    return set_mode(subl.view, self.mode)


@emvee_action("clear_selection")
class ClearSelection(EmveeAction):
  def __init__(self, amount):
    pass

  def run(self, subl, edit):
    selection = list(subl.view.sel())
    subl.view.sel().clear()

    # Flatten the existing selections.
    for index in range(len(selection)):
      region = selection[index]
      region.a = region.b
      selection[index] = region
    subl.view.sel().add_all(selection)

@emvee_action('move_by_char')
class MoveByChar(EmveeAction):
  def __init__(self, amount, *, forward=False, extend=False):
    self.amount = amount
    self.forward = bool(forward)
    self.extend = bool(extend)

  def run(self, subl, edit):
    args = {
      'forward': self.forward,
      'extend': self.extend,
      'by': 'characters',
    }
    for _ in range(self.amount):
      subl.view.run_command('move', args)


@emvee_action('move_by_line')
class MoveByLine(EmveeAction):
  def __init__(self, amount, *, forward=False, extend=False):
    self.amount = amount
    self.forward = bool(forward)
    self.extend = bool(extend)

  def run(self, subl, edit):
    args = {
      'forward': self.forward,
      'extend': self.extend,
      'by': 'lines'
    }
    for _ in range(self.amount):
      subl.view.run_command('move', args)


@emvee_action('move_by_word_begin')
class MoveByWordBegin(EmveeAction):
  def __init__(self, amount, *, forward=False, extend=False):
    self.amount = amount
    self.forward = bool(forward)
    self.extend = bool(extend)

  def run(self, subl, edit):
    args = {
      'forward': self.forward,
      'extend': self.extend,
      'by': 'words'
    }

    for _ in range(self.amount):
      subl.view.run_command('move', args)


@emvee_action('move_by_word_end')
class MoveByWordEnd(EmveeAction):
  def __init__(self, amount, *, forward=False, extend=False):
    self.amount = amount
    self.forward = bool(forward)
    self.extend = bool(extend)

  def run(self, subl, edit):
    args = {
      'forward': self.forward,
      'extend': self.extend,
      'by': 'word_ends'
    }

    for _ in range(self.amount):
      subl.view.run_command('move', args)


@emvee_action('move_by_subword_begin')
class MoveBySubwordBegin(EmveeAction):
  def __init__(self, amount, *, forward=False, extend=False):
    self.amount = amount
    self.forward = bool(forward)
    self.extend = bool(extend)

  def run(self, subl, edit):
    args = {
      'forward': self.forward,
      'extend': self.extend,
      'by': 'subwords'
    }

    for _ in range(self.amount):
      subl.view.run_command('move', args)


@emvee_action('move_by_subword_end')
class MoveBySubwordEnd(EmveeAction):
  def __init__(self, amount, *, forward=False, extend=False):
    self.amount = amount
    self.forward = bool(forward)
    self.extend = bool(extend)

  def run(self, subl, edit):
    args = {
      'forward': self.forward,
      'extend': self.extend,
      'by': 'subword_ends'
    }

    for _ in range(self.amount):
      subl.view.run_command('move', args)


@emvee_action('move_to_line_limit')
class MoveToLineLimit(EmveeAction):
  def __init__(self, amount, *, forward=False, extend=False):
    self.amount = amount
    self.forward = bool(forward)
    self.extend = bool(extend)

  def run(self, subl, edit):
    args = {
      'extend': self.extend,
      'to': 'eol' if self.forward else 'bol'
    }
    for _ in range(self.amount):
      subl.view.run_command('move_to', args)


@emvee_action('move_by_empty_line')
class MoveByEmptyLine(EmveeAction):
  def __init__(self, amount, *, forward=False, extend=False):
    self.amount = amount
    self.forward = bool(forward)
    self.extend = bool(extend)

  def run(self, subl, edit):
    selection = list(subl.view.sel())
    subl.view.sel().clear()
    region = selection[0] if len(selection) > 0 else sublime.Region(0, 0)
    for _ in range(self.amount):
      region.b = subl.view.find_by_class(region.b, self.forward, sublime.CLASS_EMPTY_LINE)

    if not self.extend:
      region.a = region.b

    subl.view.sel().add(region)
    subl.view.show(subl.view.sel(), True)


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

