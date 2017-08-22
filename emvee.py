import sublime, sublime_plugin
import threading
import sys
import difflib

def is_valid_region(reg):
  return reg \
     and type(reg) == sublime.Region \
     and reg.a >= 0 \
     and reg.b >= 0

actionLookup_Class2Name = {}
actionLookup_Name2Class = {}

def emvee_action(actionName):
  '''Note: This is a decorator.'''
  def helper(actionClass):
    actionLookup_Name2Class[actionName] = actionClass
    actionLookup_Class2Name[actionClass] = actionName
    return actionClass
  return helper


NORMAL_MODE = 'NORMAL'
INSERT_MODE = 'INSERT'
allModes = (NORMAL_MODE, INSERT_MODE)

def set_mode(view, newMode):
  result = True
  oldMode = get_mode(view)
  # print(oldMode, "=>", newMode)
  if newMode == NORMAL_MODE:
    view.settings().set('inverse_caret_state', True)
    view.settings().set('command_mode', True)
    view.settings().set('emvee_mode', NORMAL_MODE)
    display_info(view, NORMAL_MODE, context='New mode:')
  elif newMode == INSERT_MODE:
    view.settings().set('command_mode', False)
    view.settings().set('inverse_caret_state', False)
    view.settings().set('emvee_mode', INSERT_MODE)
    display_info(view, INSERT_MODE, context='New mode:')
  else:
    print('Invalid mode:', newMode, file=sys.stderr)
    return False
  return result

def get_mode(view):
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

class DisplayKiller:
  def __init__(self, view):
    self.cancel = False
    self.view = view

  def __call__(self):
    if not self.cancel:
      self.view.hide_popup()

activeDisplayKillers = {}
def display_info(view, info, *, context, force=False, fg='var(--foreground)', bg='var(--background)'):
  htmlTemplate = '<body style="color: {fg}; background-color: {bg}; margin: 0; padding: 1rem;">{context}<div style="font-size: 3rem; font-weight: bold;">{info}</div> </body>'
  content = htmlTemplate.format(context=context, info=info, fg=fg, bg=bg)
  success = False
  if view.is_popup_visible():
    view.update_popup(content)
  else:
    pos = find_display_pos(view, force=force)
    if pos >= 0:
      success = True
      view.show_popup(content, 0, pos)

  if success:
    global activeDisplayKillers
    if view.id() in activeDisplayKillers:
      activeDisplayKillers[view.id()].cancel = True

    newKiller = DisplayKiller(view)
    activeDisplayKillers[view.id()] = newKiller

    timeout = 2 * 1000 # milliseconds
    sublime.set_timeout(newKiller, timeout)

def find_display_pos(view, *, force):
  '''Find a position in the current view that is suitable for display information.'''
  visible = view.visible_region()
  visibleLines = view.lines(visible)

  result = -1
  if force or len(visibleLines) >= 8:
    firstLine = visibleLines[0]
    lastLine = visibleLines[-1]

    firstLineInLayout = view.text_to_layout(firstLine.begin())
    lastLineInLayout = view.text_to_layout(lastLine.begin())
    firstSelectionInLayout = view.text_to_layout(view.sel()[0].begin())

    deltaToFirstLine = abs(firstLineInLayout[1] - firstSelectionInLayout[1])
    deltaToLastLine = abs(lastLineInLayout[1] - firstSelectionInLayout[1])

    upperBias = 1.0
    lowerBias = 5.0

    # Choose whichever line is furthest.
    if upperBias * deltaToFirstLine > lowerBias * deltaToLastLine:
      result = firstLine.begin()
    else:
      result = lastLine.begin()
  return result

# Called when the plugin is unloaded (e.g., perhaps it just got added to
# ignored_packages). Ensure files aren't left in command mode.
def plugin_unloaded():
  for window in sublime.windows():
    for view in window.views():
      # TODO: Is it enough to set the mode to INSERT? We are being unloaded
      # afterall so only resetting certain built-in variables might be enough.
      set_mode(view, INSERT_MODE)

def plugin_loaded():
  for window in sublime.windows():
    for view in window.views():
      if view.settings().get('emvee_start_in_normal_mode'):
        set_mode(view, NORMAL_MODE)

class EmveeEventListener(sublime_plugin.EventListener):
  def on_load(self, view):
    if view.settings().get('emvee_start_in_normal_mode', True):
      set_mode(view, NORMAL_MODE)
    else:
      set_mode(view, INSERT_MODE)

  def on_query_context(self, view, key, operator, operand, match_all):
    isEnabled = view.settings().get('emvee_enabled', True)
    if not isEnabled or key == 'emvee_early_out':
      return False

    if key == 'emvee_current_mode':
      if operator == sublime.OP_EQUAL:     return operand == get_mode(view)
      if operator == sublime.OP_NOT_EQUAL: return operand != get_mode(view)
    elif key == 'emvee_is_in_normal_mode':
      isInNormalMode = get_mode(view) == NORMAL_MODE
      return operand == isInNormalMode
    elif key == 'emvee_display_current_mode':
      if view.is_popup_visible():
        view.hide_popup()
      else:
        display_info(view, get_mode(view), force=True, context='Current mode:')
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
      nameMatchThreshold = 0.6
      matches = []
      for name in actionLookup_Name2Class:
        if difflib.SequenceMatcher(None, action, name).ratio() > nameMatchThreshold:
          matches.append(name)
      if matches:
        print('Did you mean:', *matches, sep='\n  ', file=sys.stderr)
      return

    global currentState

    actionInstance = actionClass(currentState.amount, **kwargs)
    actionInstance.run(self, edit)
    if actionInstance.clearGlobalStateOnCompletion:
      currentState = EmveeState()

class EmveeAction:
  """Base class for emvee actions."""
  clearGlobalStateOnCompletion = True

@emvee_action("enter_insert_mode")
class EnterInsertMode(EmveeAction):
  def __init__(self, amount, *, append=False, location='current'):
    '''location: current, line_limit'''
    self.amount = amount or 1
    self.append = bool(append)
    self.location = location

  def run(self, subl, edit):
    currentState.activeInsertAction = self

    if self.location == 'current':
      if self.append:
        selection = []
        for region in subl.view.sel():
          isExtended = region.size() > 0
          if not (subl.view.classify(region.b) & sublime.CLASS_LINE_END):
            region.b += 1
          if not isExtended:
            region.a = region.b
          selection.append(region)
        subl.view.sel().clear();
        subl.view.sel().add_all(selection);
      else:
        pass # Stay where we are and enter insert mode.
    elif self.location == 'line_limit':
      if self.append:
        subl.view.run_command('move_to', { 'to': 'hardeol', 'extend': False })
      else:
        subl.view.run_command('move_to', { 'to': 'hardbol', 'extend': False })

    set_mode(subl.view, INSERT_MODE)

@emvee_action("exit_insert_mode")
class ExitInsertMode(EmveeAction):
  def __init__(self, amount):
    self.amount = amount or 1

  def run(self, subl, edit):
    set_mode(subl.view, NORMAL_MODE)
    # TODO Apply inserted text `currentState.INSERT_MODE.amount` times?
    currentState.activeInsertAction = None

@emvee_action("clear_state")
class ClearState(EmveeAction):
  def __init__(self, amount):
    self.amount = amount or 1
    self.clearGlobalStateOnCompletion = False

  def run(self, subl, edit):
    global currentState
    currentState = EmveeState()

@emvee_action("push_digit")
class PushDigit(EmveeAction):
  def __init__(self, _, *, digit):
    self.digit = int(digit)
    self.clearGlobalStateOnCompletion = False

  def run(self, subl, edit):
    print("push digit!", self.digit)
    oldAmount = currentState.amount or 0
    newAmount = oldAmount * 10 + self.digit
    currentState.amount = newAmount
    display_info(subl.view, str(newAmount), force=True, context='Prefix:')


@emvee_action("flatten_selections")
class FlattenSelections(EmveeAction):
  def __init__(self, amount):
    pass

  def run(self, subl, edit):
    selection = []
    for reg in subl.view.sel():
      if reg.a < reg.b and get_mode(subl.view) == NORMAL_MODE:
        reg.b -= 1
      reg.a = reg.b
      selection.append(reg)

    subl.view.sel().clear()
    subl.view.sel().add_all(selection)

@emvee_action('flip_cursors_within_selections')
class FlipCursorsWithinSelections(EmveeAction):
  def __init__(self, amount):
    self.amount = amount or 1

  def run(self, subl, edit):
    selection = []
    for reg in subl.view.sel():
      reg.a, reg.b = reg.b, reg.a
      selection.append(reg)

    subl.view.sel().clear()
    subl.view.sel().add_all(selection)

@emvee_action('move_by_char')
class MoveByChar(EmveeAction):
  def __init__(self, amount, *, forward=False, extend=False, stayInLine=False):
    self.amount = amount or 1
    self.forward = bool(forward)
    self.extend = bool(extend)
    self.stayInLine = bool(stayInLine)

  def run(self, subl, edit):
    advance = self.amount if self.forward else -self.amount
    selection = []
    for region in subl.view.sel():
      line = subl.view.lines(region)[-1]
      region.b += advance
      if self.stayInLine:
        if region.b < line.a:
          region.b = line.a
        if region.b > line.b:
          region.b = line.b
      if not self.extend:
        region.a = region.b
      selection.append(region)
    subl.view.sel().clear();
    subl.view.sel().add_all(selection);


@emvee_action('move_by_line')
class MoveByLine(EmveeAction):
  def __init__(self, amount, *, forward=False, extend=False):
    self.amount = amount or 1
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
    self.amount = amount or 1
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
    self.amount = amount or 1
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
    self.amount = amount or 1
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
    self.amount = amount or 1
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
    self.amount = amount or 1
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
    self.amount = amount or 1
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
    self.amount = amount or 1
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

@emvee_action('select_line')
class ExpandSelectionToLine(EmveeAction):
  def __init__(self, amount, *, extend=False, complete_partial_lines=False, full_line=True):
    self.extend = bool(extend)
    self.completePartialLines = bool(complete_partial_lines)
    self.fullLine = bool(full_line)

  def run(self, subl, edit):
    getter = subl.view.full_line if self.fullLine else subl.view.line
    selection = []

    if self.completePartialLines:
      for reg in subl.view.sel():
        isCursorInFront = reg.a <= reg.b
        lineA = getter(reg.a)
        lineB = getter(reg.b)
        reg.a = min(lineA.a, lineB.a)
        reg.b = max(lineA.b, lineB.b)
        if not isCursorInFront:
          reg.a, reg.b = reg.b, reg.a
        selection.append(reg)
    else:
      for reg in subl.view.sel():
        line = getter(reg.b)
        reg.b = line.b
        if not self.extend:
          reg.a = line.a
        selection.append(reg)

    subl.view.sel().clear()
    subl.view.sel().add_all(selection)

    if len(selection) == 1:
      subl.view.show(selection[0], False)

import time
class FilterSelectionCallback:
  def __init__(self):
    self.limit = None
    self.forward = True
    self.parentView = None
    self.panelView = None
    self.originalSelection = []
    self.workingSelection = []

  def onChange(self, pattern):
    try:
      # Find all matches per line.
      # `lineMatches` is a list of lists: [[ma0, ma1, ..., maN], [mb0, mb1, ..., mbN], ...]
      lineMatches = []
      for reg in self.workingSelection:
        matchesInThisRegion = []
        searchCursor = reg.begin()
        endCursor = reg.end()
        startTime = time.time()
        while True:
          matchReg = self.parentView.find(pattern, searchCursor)
          newSearchCursor = matchReg.end() + 1
          if not is_valid_region(matchReg) or newSearchCursor >= endCursor:
            break
          matchesInThisRegion.append(matchReg)
          print(searchCursor, '=>', newSearchCursor)
          searchCursor = newSearchCursor
          if time.time() - startTime > 2:
            raise Exception('timeout.')
        print(matchesInThisRegion)
        lineMatches.append(matchesInThisRegion)

      # Filter per-line matches
      newSelection = []
      if self.limit is None:
        for match in lineMatches:
          newSelection.extend(match)
      else:
        # Extract the matches according to the given limit.
        if self.forward:
          for matches in lineMatches:
            filtered = matches[:self.limit]
            newSelection.extend(filtered)
        else:
          for matches in lineMatches:
            filtered = matches[-self.limit:]
            newSelection.extend(filtered)

      # for reg in self.workingSelection:
      #   # TODO: Be case-sensitive depending on current settings.
      #   queryReg = reg
      #   while True:
      #     matchReg = self.parentView.find(pattern, queryReg)
      #     if matchReg:
      #       newSelection.append(matchReg)
      #       queryReg = matchReg
      #     else:
      #       break

      # matches = self.parentView.find_all(pattern)
      # newSelection = []
      # for match in matches:
      #   for reg in self.workingSelection:
      #     if match.begin() >= reg.begin() and match.end() <= reg.end():
      #       newSelection.append(match)

      self.parentView.sel().clear()
      if len(newSelection) == 0:
        newSelection = self.originalSelection
      self.parentView.sel().add_all(newSelection)
    except:
      pass
  def onDone(self, pattern):
    pass
  def onCancel(self):
    self.parentView.sel().clear()
    self.parentView.sel().add_all(self.originalSelection)

@emvee_action('filter_selection')
class FilterSelection(EmveeAction):
  def __init__(self, amount, *, forward):
    self.amount = amount # May be `None`
    self.forward = forward

  def run(self, subl, edit):
    view = subl.view
    window = view.window()
    originalSelection = list(subl.view.sel())

    # For each empty selection, we consider the entire line of that cursor.
    workingSelection = []
    for region in originalSelection:
      if region.begin() == region.end():
        line = view.line(region)
        workingSelection.append(line)
      else:
        workingSelection.append(region)

    cb = FilterSelectionCallback()
    cb.limit = self.amount
    cb.forward = self.forward
    cb.parentView = view
    cb.originalSelection = originalSelection
    cb.workingSelection = workingSelection
    cb.panelView = window.show_input_panel('Pattern', '', cb.onDone, cb.onChange, cb.onCancel)
    cb.panelView.set_syntax_file('Packages/Regular Expressions/RegExp.sublime-syntax')
    cb.panelView.settings().set('line_numbers', False)
    # cb.panelView.settings().set('command_mode', False)
    cb.panelView.settings().set('gutter', False)
    cb.panelView.settings().set('emvee_enabled', False)

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
        print('line operations only support positive deltas.', file=sys.stderr)

    if get_mode(subl.view) == 'select':
      set_mode(subl.view, NORMAL_MODE)


@emvee_action("swap_lines")
class SwapLines(EmveeAction):
  def __init__(self, amount, *, forward=True):
    self.amount = amount or 1
    self.forward = bool(forward)

  def run(self, subl, edit):
    cmdStr = 'swap_line_down' if self.forward else 'swap_line_up'
    for _ in range(self.amount):
      subl.view.run_command(cmdStr)


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

@emvee_action("integer_add")
class IntegerAdd(EmveeAction):
  def __init__(self, amount, delta):
    self.amount = amount or 1
    self.delta = delta

  def run(self, subl, edit):
    for reg in subl.view.sel():
      if reg.a == reg.b:
        reg = subl.view.word(reg)
        try:
          potentialReg = sublime.Region(reg.begin() - 1, reg.end())
          word = subl.view.substr(potentialReg)
          if word.startswith('-'):
            reg = potentialReg
        except:
          pass

      word = subl.view.substr(reg)
      try:
        value = int(word)
      except:
        continue
      value += self.delta
      newWord = str(value)
      subl.view.replace(edit, reg, newWord)

@emvee_action("insert_line")
class InsertLine(EmveeAction):
  def __init__(self, amount, above):
    self.amount = amount or 1
    self.above = bool(above)

  def run(self, subl, edit):
    if self.above:
      subl.view.run_command('move_to', { 'to': 'hardbol' })
    else:
      subl.view.run_command('move_to', { 'to': 'hardeol' })

    for _ in range(self.amount):
      subl.view.run_command('insert', { 'characters': '\n' })

    if self.above:
      subl.view.run_command('move', { 'by': 'lines', 'forward': False })
      subl.view.run_command('reindent', { 'force_indent': False })

    if get_mode(subl.view) != INSERT_MODE:
      subl.view.run_command('emvee', { 'action': 'enter_insert_mode' })
