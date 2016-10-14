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


normalMode = 'NORMAL'
insertMode = 'INSERT'
allModes = (normalMode, insertMode)


def set_mode_raw(view, newMode):
  oldMode = get_mode(view)
  print(oldMode, "=>", newMode)
  view.settings().set('emvee_mode', str(newMode))

def set_mode(view, newMode):
  if newMode not in allModes:
    print("Invalid mode:", newMode, file=sys.stderr)
    return False
  set_mode_raw(view, newMode)
  return True

def get_mode(view):
  if not view.settings().has('emvee_mode'):
    view.settings().set('emvee_mode', normalMode)
  mode = view.settings().get('emvee_mode')
  return mode

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

def display_mode(view, mode, fg='var(--foreground)', bg='var(--background)'):
  htmlTemplate = '<body style="color: {fg}; background-color: {bg}; margin: 0; padding: 1rem;"> Mode <div style="font-size: 3rem; font-weight: bold;">{mode}</div> </body>'
  pos = view.visible_region().begin()
  view.show_popup(htmlTemplate.format(mode=mode, fg=fg, bg=bg), 0, pos)


class EmveeEventListener(sublime_plugin.EventListener):
  def on_load(self, view):
    # set_mode(view, normalMode)
    pass

  def on_query_context(self, view, key, operator, operand, match_all):
    if key == 'emvee_early_out':
      return False

    if key == 'emvee_current_mode':
      if operator == sublime.OP_EQUAL:     return operand == get_mode(view)
      if operator == sublime.OP_NOT_EQUAL: return operand != get_mode(view)
    elif key == 'emvee_display_current_mode':
      display_mode(view, get_mode(view))
      return False


class EmveeState:
  def __init__(self):
    self.amount = None
    self.activeInsertAction = None

currentState = EmveeState()


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

    amount = currentState.amount or 1

    actionInstance = actionClass(amount, **kwargs)
    actionInstance.run(self, edit)

class EmveeAction:
  """Base class for emvee actions."""
  pass

@emvee_action("enter_insert_mode")
class EnterInsertMode(EmveeAction):
  def __init__(self, amount):
    self.amount = amount

  def run(self, subl, edit):
    currentState.activeInsertAction = self
    subl.view.settings().set("command_mode", False)
    subl.view.settings().set('inverse_caret_state', False)
    set_mode(subl.view, insertMode)
    display_mode(subl.view, 'INSERT')

@emvee_action("exit_insert_mode")
class ExitInsertMode(EmveeAction):
  def __init__(self, amount):
    self.amount = amount

  def run(self, subl, edit):
    set_mode(subl.view, normalMode)
    subl.view.settings().set('inverse_caret_state', True)
    subl.view.settings().set("command_mode", True)
    # TODO Apply inserted text `currentState.insertMode.amount` times?
    currentState.activeInsertAction = None
    display_mode(subl.view, 'NORMAL')

@emvee_action("clear_state")
class ClearState(EmveeAction):
  def __init__(self, amount):
    self.amount = amount

  def run(self, subl, edit):
    global currentState
    currentState = EmveeState()


@emvee_action("flatten_selection")
class FlattenSelection(EmveeAction):
  def __init__(self, amount):
    pass

  def run(self, subl, edit):
    selection = []
    for reg in subl.view.sel():
      if reg.a != reg.b:
        reg.b -= 1 # TODO: Only do this in inverse_caret_state!
        reg.a = reg.b
      selection.append(reg)

    subl.view.sel().clear()
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
  def __init__(self, amount, *, lines=0, screensX=0, screensY=0, centerCursor=False):
    self.amount = amount
    self.lines = lines
    self.screensX = screensX
    self.screensY = screensY
    self.centerCursor = centerCursor

  def run(self, subl, edit):
    lines = self.lines
    screensY = self.screensY
    screensX = self.screensX

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

    if self.centerCursor:
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
      set_mode(subl.view, normalMode)


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

