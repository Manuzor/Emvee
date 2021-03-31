import sublime, sublime_plugin
import threading
import sys
import difflib
import datetime

LOG_LEVEL_ERROR = 1
LOG_LEVEL_DEBUG = 0
LOG_LEVEL = LOG_LEVEL_ERROR
# LOG_LEVEL = LOG_LEVEL_DEBUG

def debug_log(*args):
  if LOG_LEVEL <= LOG_LEVEL_DEBUG:
    ts = datetime.datetime.now().time()
    print(ts, "emvee:", "[DEBUG]", *args, file=sys.stderr)

def err(*args):
  if LOG_LEVEL <= LOG_LEVEL_ERROR:
    ts = datetime.datetime.now().time()
    print(ts, "emvee:", "[ERROR]", *args, file=sys.stderr)


def is_valid_region(reg):
  return reg \
     and type(reg) == sublime.Region \
     and reg.a >= 0 \
     and reg.b >= 0

def next_line_point(view, point, increment):
  row, col = view.rowcol(point)
  result = view.text_point(row + increment, col)
  return result

NORMAL_MODE = 'NORMAL'
INSERT_MODE = 'INSERT'
SELECT_MODE = 'SELECT'
all_modes = (NORMAL_MODE, INSERT_MODE, SELECT_MODE)

def set_mode(view, new_mode, show_info=True):
  old_mode = get_mode(view)
  debug_log(old_mode, "=>", new_mode)
  inverse_caret_state = None
  command_mode = None
  if new_mode == NORMAL_MODE:
    command_mode = True
    inverse_caret_state = True
  elif new_mode == INSERT_MODE:
    command_mode = False
    inverse_caret_state = False
  elif new_mode == SELECT_MODE:
    command_mode = True
    inverse_caret_state = True
  else:
    err('Invalid mode:', new_mode)
    return False
  view.settings().set('command_mode', command_mode)
  view.settings().set('inverse_caret_state', inverse_caret_state)
  view.settings().set('emvee_mode', new_mode)
  if show_info:
    show_display_info(view, new_mode, context='New mode:', force=(LOG_LEVEL <= LOG_LEVEL_DEBUG))
  return True

def get_mode(view):
  mode = view.settings().get('emvee_mode')
  return mode

class Delay:
  delaysInFlight = {}
  instanceCounter = 0

  @classmethod
  def reset(cls, id, timeout_ms, callback):
    '''Execute callback after timeout, cancel previous one if it exists.'''
    cls.cancel(id)
    cls.instanceCounter += 1

    delay = Delay()
    delay.id = cls.instanceCounter
    delay.done = False
    def wrapped_callback():
      if delay.done:
        debug_log('delay[{},{}] NOT executing (already done)'.format(id, delay.id))

        return
      debug_log('delay[{},{}] executing'.format(id, delay.id))
      callback()
      delay.done = True

    cls.delaysInFlight[id] = delay
    sublime.set_timeout(wrapped_callback, timeout_ms)
    debug_log('delay[{},{}] set'.format(id, delay.id))

  @classmethod
  def cancel(cls, id):
    prevDelay = cls.delaysInFlight.get(id, None)
    if prevDelay and not prevDelay.done:
      debug_log('delay[{},{}] cancelling'.format(id, prevDelay.id))
      prevDelay.done = True


def show_display_info(view, info, *, context, force=False, fg='var(--foreground)', bg='var(--background)'):
  # Disable for now.
  if not force:
    return

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
    Delay.reset(view.id(),
                timeout_ms = 2 * 1000,
                callback = view.hide_popup)

def hide_display_info(view):
  if view.is_popup_visible():
    Delay.cancel(view.id())
    view.hide_popup()

def find_display_pos(view, *, force):
  '''Find a position in the current view that is suitable for display information.'''
  visible = view.visible_region()
  visible_lines = view.lines(visible)

  result = -1
  if force or len(visible_lines) >= 8:
    first_line = visible_lines[0]
    last_line = visible_lines[-1]

    first_line_in_layout = view.text_to_layout(first_line.begin())
    last_line_in_layout = view.text_to_layout(last_line.begin())
    first_selection_in_layout = view.text_to_layout(view.sel()[0].begin())

    deltaToFirstLine = abs(first_line_in_layout[1] - first_selection_in_layout[1])
    deltaToLastLine = abs(last_line_in_layout[1] - first_selection_in_layout[1])

    upper_bias = 1.0
    lower_bias = 5.0

    # Choose whichever line is furthest.
    if upper_bias * deltaToFirstLine > lower_bias * deltaToLastLine:
      result = first_line.begin()
    else:
      result = last_line.begin()
  return result

def get_default_mode(view):
  if view.settings().get('emvee_start_in_normal_mode', True):
    return NORMAL_MODE
  return INSERT_MODE

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
      set_mode(view, get_default_mode(view))

class EmveeEventListener(sublime_plugin.EventListener):
  def on_new(self, view):
    set_mode(view, INSERT_MODE, show_info=False)

  def on_load(self, view):
    set_mode(view, get_default_mode(view))

  def on_query_context(self, view, key, operator, operand, match_all):
    global current_state

    is_enabled = view.settings().get('emvee_enabled', True)
    if not is_enabled:
      set_mode(view, None)
      return

    if key == 'emvee_display_current_mode':
      if view.is_popup_visible():
        hide_display_info(view)
      else:
        amount = current_state.amount or 1
        show_display_info(view, get_mode(view), force=True, context='Current mode [{}]'.format(amount))
      return False

    hide_display_info(view)

    if key == 'emvee_current_mode':
      if operand:
        allowedModes = [x for x in operand.split(',') if x]
        if operator == sublime.OP_EQUAL:     return get_mode(view)     in allowedModes
        if operator == sublime.OP_NOT_EQUAL: return get_mode(view) not in allowedModes
      else:
        err('missing operand for', key)
      return True

    if key == 'emvee_clear_state':
      current_state = EmveeState()
      return True

    if key == 'emvee_early_out':
      return False

class EmveeState:
  def __init__(self):
    self.amount = None

current_state = EmveeState()

class EmveeCommand(sublime_plugin.TextCommand):
  def run(self, edit, *, action, **kwargs):
    global current_state

    view = self.view
    amount = current_state.amount or 1
    if amount < 1:
      amount = 1

    all_actions = set()
    def wants_action(name):
      all_actions.add(name)
      if name != action:
          return False
      debug_log('action:', action)
      return True

    def consume_amount():
      current_state.amount = None

    if wants_action('enter_normal_mode'):
      consume_amount()
      # ExitInsertMode(current_state.amount, **kwargs).run(self, edit)
      selection = []
      for region in view.sel():
        region.a = region.b
        selection.append(region)
      view.sel().clear()
      view.sel().add_all(selection)
      set_mode(view, NORMAL_MODE)

    elif wants_action('enter_insert_mode'):
      consume_amount()
      # EnterInsertMode(current_state.amount, **kwargs).run(self, edit)
      location = kwargs.get('location', 'current')
      append = bool(kwargs.get('append', False))
      if location == 'current':
        if append:
          selection = []
          for region in view.sel():
            isExtended = region.size() > 0
            if not (view.classify(region.b) & sublime.CLASS_LINE_END):
              region.b += 1
            if not isExtended:
              region.a = region.b
            selection.append(region)
          view.sel().clear();
          view.sel().add_all(selection);
        else:
          pass # Stay where we are and enter insert mode.
      elif location == 'line_limit':
        if append:
          view.run_command('move_to', { 'to': 'hardeol', 'extend': False })
        else:
          view.run_command('move_to', { 'to': 'hardbol', 'extend': False })
      set_mode(view, INSERT_MODE)

    elif wants_action('push_digit'):
      # PushDigit(current_state.amount, **kwargs).run(self, edit)
      digit = int(kwargs.get('digit', 1))
      print('foo', digit)

      try:
        new_amount = int(current_state.amount) * 10 + digit
      except:
        new_amount = digit
      if new_amount > 9999:
        new_amount = 9999 # TODO: What should this limit be?
      current_state.amount = new_amount
      show_display_info(view, str(new_amount), force=True, context='Prefix:')

    elif wants_action('flatten_selections'):
      consume_amount()
      FlattenSelections(current_state.amount, **kwargs).run(self, edit)

    elif wants_action('flip_cursors_within_selections'):
      consume_amount()
      FlipCursorsWithinSelections(current_state.amount, **kwargs).run(self, edit)

    elif wants_action('move_by_char'):
      consume_amount()
      # MoveByChar(current_state.amount, **kwargs).run(self, edit)
      forward = bool(kwargs.get('forward', True))
      extend = get_mode(view) == SELECT_MODE # bool(kwargs.get('extend', False))
      stay_in_line = bool(kwargs.get('stay_in_line', False))
      advance = amount if forward else -amount
      selection = []
      for region in view.sel():
        line = view.lines(region)[-1]
        region.b += advance
        if stay_in_line:
          if region.b < line.a:
            region.b = line.a
          if region.b > line.b:
            region.b = line.b
        if not extend:
          region.a = region.b
        selection.append(region)
      view.sel().clear();
      view.sel().add_all(selection);

    elif wants_action('move_by_line'):
      consume_amount()
      # MoveByLine(current_state.amount, **kwargs).run(self, edit)
      forward = bool(kwargs.get('forward', True))
      extend = get_mode(view) == SELECT_MODE # bool(kwargs.get('extend', False))
      args = {
        'forward': forward,
        'extend': extend,
        'by': 'lines'
      }
      for _ in range(amount):
        view.run_command('move', args)

    elif wants_action('move_by_word_begin'):
      consume_amount()
      # MoveByWordBegin(current_state.amount, **kwargs).run(self, edit)
      forward = bool(kwargs.get('forward', True))
      extend = get_mode(view) == SELECT_MODE # bool(kwargs.get('extend', False))
      args = {
        'forward': forward,
        'extend': extend,
        'by': 'words'
      }
      for _ in range(amount):
        view.run_command('move', args)

    elif wants_action('move_by_word_end'):
      consume_amount()
      # MoveByWordEnd(current_state.amount, **kwargs).run(self, edit)
      forward = bool(kwargs.get('forward', True))
      extend = get_mode(view) == SELECT_MODE # bool(kwargs.get('extend', False))
      args = {
        'forward': forward,
        'extend': extend,
        'by': 'word_ends'
      }
      for _ in range(amount):
        view.run_command('move', args)

    elif wants_action('move_by_subword_begin'):
      consume_amount()
      # MoveBySubwordBegin(current_state.amount, **kwargs).run(self, edit)
      forward = bool(kwargs.get('forward', True))
      extend = get_mode(view) == SELECT_MODE # bool(kwargs.get('extend', False))
      args = {
        'forward': forward,
        'extend': extend,
        'by': 'subwords'
      }
      for _ in range(amount):
        view.run_command('move', args)

    elif wants_action('move_by_subword_end'):
      consume_amount()
      # MoveBySubwordEnd(current_state.amount, **kwargs).run(self, edit)
      forward = bool(kwargs.get('forward', True))
      extend = get_mode(view) == SELECT_MODE # bool(kwargs.get('extend', False))
      args = {
        'forward': forward,
        'extend': extend,
        'by': 'subword_ends'
      }

      for _ in range(amount):
        view.run_command('move', args)

    elif wants_action('move_to_line_limit'):
      consume_amount()
      # MoveToLineLimit(current_state.amount, **kwargs).run(self, edit)
      forward = bool(kwargs.get('forward', True))
      extend = get_mode(view) == SELECT_MODE # bool(kwargs.get('extend', False))
      args = {
        'extend': extend,
        'to': 'eol' if forward else 'bol'
      }
      for _ in range(amount):
        view.run_command('move_to', args)

    elif wants_action('move_by_empty_line'):
      consume_amount()
      # MoveByEmptyLine(current_state.amount, **kwargs).run(self, edit)
      forward = bool(kwargs.get('forward', True))
      select = bool(kwargs.get('select', False))
      if select and get_mode(view) != SELECT_MODE:
        set_mode(view, SELECT_MODE)

      extend = get_mode(view) == SELECT_MODE
      ignore_whitespace = bool(kwargs.get('ignore_whitespace', True))

      selection = []
      if ignore_whitespace:
        # search for empty or "white" lines.
        increment = amount if forward else -amount
        for region in view.sel():
          row, col = view.rowcol(region.b)
          col = 0
          search_point = view.text_point(row, col)
          found_non_empty_line = False
          while True:
            line_region = view.line(search_point)
            line = view.substr(line_region)
            line_is_empty = len(line.strip()) == 0
            if line_is_empty:
              if found_non_empty_line:
                break
            else:
              found_non_empty_line = True
            old_search_point = search_point
            search_point = next_line_point(view, search_point, increment=increment)
            if search_point == old_search_point:
              break

          region.b = search_point
          if not extend:
            region.a = region.b

          selection.append(region)
      else:
        # Use built-in find_by_class
        for region in view.sel():
          region.b = view.find_by_class(region.b, forward, sublime.CLASS_EMPTY_LINE)
          if not extend:
            region.a = region.b
          selection.append(region)

      view.sel().clear()
      view.sel().add_all(selection)
      view.show(view.sel(), True)

      if end_up_in_select_mode and get_mode(view) != SELECT_MODE:
        set_mode(view, SELECT_MODE)

    elif wants_action('scroll'):
      consume_amount()
      # Scroll(current_state.amount, **kwargs).run(self, edit)
      # return
      lines = float(kwargs.get('lines', 0))
      screens_x = float(kwargs.get('delta_screens_x', 0))
      screens_y = float(kwargs.get('delta_screens_y', 0))
      center_cursor = bool(kwargs.get('center_cursor', False))

      print('screens_y', screens_y)

      if screens_y:
        extent = view.viewport_extent()
        lines_per_screen = extent[1] / view.line_height()
        lines += screens_y * lines_per_screen

      if lines:
        view.run_command('scroll_lines', { 'amount': lines })

      if screens_x:
        position = view.viewport_position()
        extent = view.viewport_extent()
        maxExtent = view.layout_extent()
        max_x = maxExtent[0] - extent[0]
        if max_x > 0:
          offset_x = screens_x * extent[0]
          new_x = position[0] + offset_x
          new_x = max(0, min(new_x, max_x))
          new_position = (new_x, position[1])
          view.set_viewport_position(new_position)

      if center_cursor:
        selection = view.sel()
        if len(selection) > 1:
          view.show(view.sel(), True)
        else:
          extent = view.show_at_center(selection[0])

    elif wants_action('select'):
      consume_amount()
      # ExpandSelectionToLine(current_state.amount, **kwargs).run(self, edit)
      extend = True # bool(kwargs.get('extend', False))
      mode = kwargs.get('mode', 'char')
      complete_partial_lines = bool(kwargs.get('complete_partial_lines', False))
      full_line = bool(kwargs.get('full_line', True))
      getter = view.full_line if full_line else view.line
      selection = []

      if mode == 'line':
        complete_partial_lines = True
        if complete_partial_lines:
          for reg in view.sel():
            is_cursor_in_front = reg.a <= reg.b
            line_a = getter(reg.a)
            line_b = getter(reg.b)
            reg.a = min(line_a.a, line_b.a)
            reg.b = max(line_a.b, line_b.b)
            if not is_cursor_in_front:
              reg.a, reg.b = reg.b, reg.a
            selection.append(reg)
        else:
          for reg in view.sel():
            line = getter(reg.b)
            reg.b = line.b
            if not extend:
              reg.a = line.a
            selection.append(reg)

        view.sel().clear()
        view.sel().add_all(selection)

        if len(selection) == 1:
          view.show(selection[0], False)

      if get_mode(view) != SELECT_MODE:
        set_mode(view, SELECT_MODE)

    elif wants_action('split_selection'):
      consume_amount()
      # SplitSelection(current_state.amount, **kwargs).run(self, edit)
      view.run_command('split_selection_by_pattern')

    elif wants_action('delete_to_eol') or wants_action('delete_line'):
      consume_amount()
      delete_full_line = action == 'delete_line'
      selection = []
      for region in view.sel():
        prev_line = None
        remaining = amount
        while remaining > 0:
          line_region = view.full_line(region.b) if remaining > 1 else view.line(region.b)
          region.b = line_region.b
          if delete_full_line and region.a > line_region.a:
            region.a = line_region.a
          remaining -= 1
        selection.append(region)
      view.sel().clear()
      view.sel().add_all(selection)

    elif wants_action('delete'):
      consume_amount()
      # Delete(current_state.amount, **kwargs).run(self, edit)
      delta = float(kwargs.get('delta', 0.0))
      by = kwargs.get('by')
      supported_args_for_by = ('char', 'word', 'line_from_cursor', 'line', 'full_line')
      if by not in supported_args_for_by:
        raise ValueError('Don\'t know "{}". Supported arguments for "by": {}'.format(by, supported_args_for_by))

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

        view.run_command('add_to_kill_ring', { 'forward': forward })
        for _ in range(amount):
          view.run_command(sublCommand)

      #
      # By word
      #
      elif by == 'word':
        for _ in range(amount):
          view.run_command('delete_word', { 'forward': forward })

      #
      # By line relative to the cursor
      #
      elif by in ('line_from_cursor', 'full_line_from_cursor'):
        sublCommand = 'right_delete' if forward else 'left_delete'
        selection = list(view.sel())
        view.sel().clear()
        func = getattr(view, 'line' if by == 'line_from_cursor' else 'full_line')
        for index in range(len(selection)):
          region = selection[index]
          row, _ = view.rowcol(region.end())
          line = func(view.text_point(row + amount - 1, 0))
          if forward:
            region = sublime.Region(region.begin(), line.end())
          else:
            region = sublime.Region(line.begin(), region.end())
          selection[index] = region
        view.sel().add_all(selection)
        view.run_command('add_to_kill_ring', { 'forward': forward })
        view.run_command(sublCommand)

      #
      # By line
      #
      elif by in ('line', 'full_line'):
        if forward:
          for _ in range(amount):
            selection = list(view.sel())
            view.sel().clear()
            func = getattr(view, by)
            for index in range(len(selection)):
              selection[index] = func(selection[index])
            view.sel().add_all(selection)
            view.run_command('add_to_kill_ring', { 'forward': forward })
          view.run_command('right_delete')
        else:
          err('line operations only support positive deltas.')

    elif wants_action('swap_cursor_with_anchor'):
      consume_amount()
      SwapCursorWithAnchor(amount, **kwargs).run(self, edit)

    elif wants_action('integer_add'):
      consume_amount()
      # IntegerAdd(amount, **kwargs).run(self, edit)
      delta = int(kwargs.get('delta', 0))
      for reg in view.sel():
        if reg.a == reg.b:
          reg = view.word(reg)
          try:
            potentialReg = sublime.Region(reg.begin() - 1, reg.end())
            word = view.substr(potentialReg)
            if word.startswith('-'):
              reg = potentialReg
          except:
            pass

        word = view.substr(reg)
        try:
          value = int(word)
        except:
          continue
        value += delta
        newWord = str(value)
        view.replace(edit, reg, newWord)

    elif wants_action('insert_line'):
      consume_amount()
      # InsertLine(amount, **kwargs).run(self, edit)
      above = bool(kwargs.get('above', False))
      if above:
        view.run_command('move_to', { 'to': 'hardbol' })
      else:
        view.run_command('move_to', { 'to': 'hardeol' })

      for _ in range(amount):
        view.run_command('insert', { 'characters': '\n' })

      if above:
        view.run_command('move', { 'by': 'lines', 'forward': False })
        view.run_command('reindent', { 'force_indent': False })

      if get_mode(view) != INSERT_MODE:
        view.run_command('emvee', { 'action': 'enter_insert_mode' })

    else:
      if not action:
        err('missing "action" parameter')
      else:
        err('No such emvee action:', action)
        name_match_threshold = 0.6
        matches = []
        for name in all_actions:
          if difflib.SequenceMatcher(None, action, name).ratio() > name_match_threshold:
            matches.append(name)
        if matches:
          err('Did you mean:', '\n  '.join(matches))

# class EmveeAction:
#   """Base class for emvee actions."""
#   clearGlobalStateOnCompletion = True

# class ExitToNormalMode(EmveeAction):
#   def __init__(self, amount):
#     self.amount = amount or 1

#   def run(self, subl, edit):
#     selection = []
#     for region in subl.view.sel():
#       region.a = region.b
#       selection.append(region)
#     subl.view.sel().clear()
#     subl.view.sel().add_all(selection)
#     set_mode(subl.view, NORMAL_MODE)

# @emvee_action("enter_insert_mode")
# class EnterInsertMode(EmveeAction):
#   def __init__(self, amount, *, append=False, location='current'):
#     '''location: current, line_limit'''
#     self.amount = amount or 1
#     self.append = bool(append)
#     self.location = location

#   def run(self, subl, edit):
#     if self.location == 'current':
#       if self.append:
#         selection = []
#         for region in subl.view.sel():
#           isExtended = region.size() > 0
#           if not (subl.view.classify(region.b) & sublime.CLASS_LINE_END):
#             region.b += 1
#           if not isExtended:
#             region.a = region.b
#           selection.append(region)
#         subl.view.sel().clear();
#         subl.view.sel().add_all(selection);
#       else:
#         pass # Stay where we are and enter insert mode.
#     elif self.location == 'line_limit':
#       if self.append:
#         subl.view.run_command('move_to', { 'to': 'hardeol', 'extend': False })
#       else:
#         subl.view.run_command('move_to', { 'to': 'hardbol', 'extend': False })

#     set_mode(subl.view, INSERT_MODE)

# @emvee_action("exit_insert_mode")
# class ExitInsertMode(ExitToNormalMode): pass

# @emvee_action("enter_select_mode")
# class EnterSelectMode(EmveeAction):
#   def __init__(self, amount, *, append=False):
#     self.amount = amount or 1
#     self.append = bool(append)

#   def run(self, subl, edit):
#     set_mode(subl.view, SELECT_MODE)

# @emvee_action("exit_select_mode")
# class ExitSelectMode(ExitToNormalMode): pass

# @emvee_action("push_digit")
# class PushDigit(EmveeAction):
#   def __init__(self, _, *, digit):
#     self.digit = int(digit)
#     self.clearGlobalStateOnCompletion = False

#   def run(self, subl, edit):
#     debug_log("push digit!", self.digit)
#     oldAmount = current_state.amount or 0
#     newAmount = oldAmount * 10 + self.digit
#     if newAmount > 9999:
#         newAmount = 9999 # TODO This is an arbitrary limit. What value should it have?
#     current_state.amount = newAmount
#     show_display_info(subl.view, str(newAmount), force=True, context='Prefix:')


# @emvee_action("flatten_selections")
# class FlattenSelections(EmveeAction):
#   def __init__(self, amount):
#     pass

#   def run(self, subl, edit):
#     selection = []
#     for reg in subl.view.sel():
#       if reg.a < reg.b and get_mode(subl.view) == NORMAL_MODE:
#         reg.b -= 1
#       reg.a = reg.b
#       selection.append(reg)

#     subl.view.sel().clear()
#     subl.view.sel().add_all(selection)

# @emvee_action('flip_cursors_within_selections')
# class FlipCursorsWithinSelections(EmveeAction):
#   def __init__(self, amount):
#     self.amount = amount or 1

#   def run(self, subl, edit):
#     selection = []
#     for reg in subl.view.sel():
#       reg.a, reg.b = reg.b, reg.a
#       selection.append(reg)

#     subl.view.sel().clear()
#     subl.view.sel().add_all(selection)

# @emvee_action('move_by_char')
# class MoveByChar(EmveeAction):
#   def __init__(self, amount, *, forward=False, extend=False, stay_in_line=False):
#     self.amount = amount or 1
#     self.forward = bool(forward)
#     self.extend = bool(extend)
#     self.stay_in_line = bool(stay_in_line)

#   def run(self, subl, edit):
#     advance = self.amount if self.forward else -self.amount
#     selection = []
#     for region in subl.view.sel():
#       line = subl.view.lines(region)[-1]
#       region.b += advance
#       if self.stay_in_line:
#         if region.b < line.a:
#           region.b = line.a
#         if region.b > line.b:
#           region.b = line.b
#       if not self.extend:
#         region.a = region.b
#       selection.append(region)
#     subl.view.sel().clear();
#     subl.view.sel().add_all(selection);


# @emvee_action('move_by_line')
# class MoveByLine(EmveeAction):
#   def __init__(self, amount, *, forward=False, extend=False):
#     self.amount = amount or 1
#     self.forward = bool(forward)
#     self.extend = bool(extend)

#   def run(self, subl, edit):
#     args = {
#       'forward': self.forward,
#       'extend': self.extend,
#       'by': 'lines'
#     }
#     for _ in range(self.amount):
#       subl.view.run_command('move', args)


# @emvee_action('move_by_word_begin')
# class MoveByWordBegin(EmveeAction):
#   def __init__(self, amount, *, forward=False, extend=False):
#     self.amount = amount or 1
#     self.forward = bool(forward)
#     self.extend = bool(extend)

#   def run(self, subl, edit):
#     args = {
#       'forward': self.forward,
#       'extend': self.extend,
#       'by': 'words'
#     }

#     for _ in range(self.amount):
#       subl.view.run_command('move', args)


# @emvee_action('move_by_word_end')
# class MoveByWordEnd(EmveeAction):
#   def __init__(self, amount, *, forward=False, extend=False):
#     self.amount = amount or 1
#     self.forward = bool(forward)
#     self.extend = bool(extend)

#   def run(self, subl, edit):
#     args = {
#       'forward': self.forward,
#       'extend': self.extend,
#       'by': 'word_ends'
#     }

#     for _ in range(self.amount):
#       subl.view.run_command('move', args)


# @emvee_action('move_by_subword_begin')
# class MoveBySubwordBegin(EmveeAction):
#   def __init__(self, amount, *, forward=False, extend=False):
#     self.amount = amount or 1
#     self.forward = bool(forward)
#     self.extend = bool(extend)

#   def run(self, subl, edit):
#     args = {
#       'forward': self.forward,
#       'extend': self.extend,
#       'by': 'subwords'
#     }

#     for _ in range(self.amount):
#       subl.view.run_command('move', args)


# @emvee_action('move_by_subword_end')
# class MoveBySubwordEnd(EmveeAction):
#   def __init__(self, amount, *, forward=False, extend=False):
#     self.amount = amount or 1
#     self.forward = bool(forward)
#     self.extend = bool(extend)

#   def run(self, subl, edit):
#     args = {
#       'forward': self.forward,
#       'extend': self.extend,
#       'by': 'subword_ends'
#     }

#     for _ in range(self.amount):
#       subl.view.run_command('move', args)


# @emvee_action('move_to_line_limit')
# class MoveToLineLimit(EmveeAction):
#   def __init__(self, amount, *, forward=False, extend=False):
#     self.amount = amount or 1
#     self.forward = bool(forward)
#     self.extend = bool(extend)

#   def run(self, subl, edit):
#     args = {
#       'extend': self.extend,
#       'to': 'eol' if self.forward else 'bol'
#     }
#     for _ in range(self.amount):
#       subl.view.run_command('move_to', args)


# @emvee_action('move_by_empty_line')
# class MoveByEmptyLine(EmveeAction):
#   def __init__(self, amount, *, forward=True, extend=False, ignore_whitespace=True):
#     self.amount = amount or 1
#     self.forward = bool(forward)
#     self.extend = bool(extend)
#     self.ignore_whitespace = bool(ignore_whitespace)

#   def run(self, subl, edit):
#     selection = []
#     if self.ignore_whitespace:
#       # search for empty or "white" lines.
#       increment = self.amount if self.forward else -self.amount
#       for region in subl.view.sel():
#         row, col = subl.view.rowcol(region.b)
#         col = 0
#         search_point = subl.view.text_point(row, col)
#         found_non_empty_line = False
#         while True:
#           line_region = subl.view.line(search_point)
#           line = subl.view.substr(line_region)
#           line_is_empty = len(line.strip()) == 0
#           if line_is_empty:
#             if found_non_empty_line:
#               break
#           else:
#             found_non_empty_line = True
#           old_search_point = search_point
#           search_point = next_line_point(subl.view, search_point, increment=increment)
#           if search_point == old_search_point:
#             break

#         region.b = search_point
#         if not self.extend:
#           region.a = region.b

#         selection.append(region)
#     else:
#       # Use built-in find_by_class
#       for region in subl.view.sel():
#         region.b = subl.view.find_by_class(region.b, self.forward, sublime.CLASS_EMPTY_LINE)
#         if not self.extend:
#           region.a = region.b
#         selection.append(region)

#     subl.view.sel().clear()
#     subl.view.sel().add_all(selection)
#     subl.view.show(subl.view.sel(), True)


# @emvee_action("scroll")
# class Scroll(EmveeAction):
#   def __init__(self, amount, *, lines=0, delta_screens_x=0, delta_screens_y=0, center_cursor=False):
#     self.amount = amount or 1
#     self.lines = lines
#     self.screens_x = delta_screens_x
#     self.screens_y = delta_screens_y
#     self.center_cursor = center_cursor

#   def run(self, subl, edit):
#     lines = self.lines
#     screens_y = self.screens_y
#     screens_x = self.screens_x

#     if screens_y:
#       extent = subl.view.viewport_extent()
#       lines_per_screen = extent[1] / subl.view.line_height()
#       lines += screens_y * lines_per_screen

#     if lines:
#       subl.view.run_command('scroll_lines', { 'amount': lines })

#     if screens_x:
#       position = subl.view.viewport_position()
#       extent = subl.view.viewport_extent()
#       maxExtent = subl.view.layout_extent()
#       max_x = maxExtent[0] - extent[0]
#       if max_x > 0:
#         offset_x = screens_x * extent[0]
#         new_x = position[0] + offset_x
#         new_x = max(0, min(new_x, max_x))
#         new_position = (new_x, position[1])
#         subl.view.set_viewport_position(new_position)

#     if self.center_cursor:
#       selection = subl.view.sel()
#       if len(selection) > 1:
#         subl.view.show(subl.view.sel(), True)
#       else:
#         extent = subl.view.show_at_center(selection[0])

# @emvee_action('select_line')
# class ExpandSelectionToLine(EmveeAction):
#   def __init__(self, amount, *, extend=False, complete_partial_lines=False, full_line=True):
#     self.extend = bool(extend)
#     self.complete_partial_lines = bool(complete_partial_lines)
#     self.fullLine = bool(full_line)

#   def run(self, subl, edit):
#     getter = subl.view.full_line if self.fullLine else subl.view.line
#     selection = []

#     if self.complete_partial_lines:
#       for reg in subl.view.sel():
#         is_cursor_in_front = reg.a <= reg.b
#         line_a = getter(reg.a)
#         line_b = getter(reg.b)
#         reg.a = min(line_a.a, line_b.a)
#         reg.b = max(line_a.b, line_b.b)
#         if not is_cursor_in_front:
#           reg.a, reg.b = reg.b, reg.a
#         selection.append(reg)
#     else:
#       for reg in subl.view.sel():
#         line = getter(reg.b)
#         reg.b = line.b
#         if not self.extend:
#           reg.a = line.a
#         selection.append(reg)

#     subl.view.sel().clear()
#     subl.view.sel().add_all(selection)

#     if len(selection) == 1:
#       subl.view.show(selection[0], False)

# class SplitSelectionByPatternInputHandler(sublime_plugin.TextInputHandler):
#   def __init__(self, view):
#     self.view = view
#     self.original_selection = list(view.sel())
#     self.show_hint = False

#   def do_split(self, pattern):
#     if not pattern:
#       return []

#     # For each empty selection, we consider the entire line of that cursor.
#     working_selection = []
#     for region in self.original_selection:
#       if region.begin() == region.end():
#         line = self.view.line(region)
#         working_selection.append(line)
#       else:
#         working_selection.append(region)

#     all_matches = self.view.find_all(pattern)
#     matches = []
#     for selection in working_selection:
#       selection_matches = []
#       for match in all_matches:
#         if selection.contains(match):
#           selection_matches.append(match)
#       if len(selection_matches):
#         matches.append((selection, selection_matches))
#     return matches;

#   def placeholder(self):
#     return "Regular Expression"

#   def preview(self, pattern):
#     view = self.view

#     split = self.do_split(pattern)

#     if not len(split):
#       return sublime.Html("<i>no matches</i>")

#     num_selections = len(split)
#     num_matches_total = sum(map(lambda x: len(x[1]), split))

#     if num_selections == 1:
#       return "{} matches".format(num_matches_total)
#     else:
#       return "{} matches in {} selections".format(num_matches_total, num_selections)

#   def validate(self, pattern):
#     return len(self.do_split(pattern)) > 0

#   def cancel(self):
#     self.view.sel().clear()
#     self.view.sel().add_all(self.original_selection)

#   def confirm(self, pattern):
#     view = self.view

#     split = self.do_split(pattern)
#     results = []
#     for match in split:
#       results.extend(match[1])
#     view.sel().clear()
#     view.sel().add_all(results)

# class SplitSelectionByPatternCommand(sublime_plugin.TextCommand):
#   def run(self, edit, split_selection_by_pattern):
#     pass

#   def input(self, args):
#     return SplitSelectionByPatternInputHandler(self.view)

# @emvee_action('split_selection')
# class SplitSelection(EmveeAction):
#   def __init__(self, amount, *, forward):
#     self.amount = amount # May be `None`
#     self.forward = forward

#   def run(self, subl, edit):
#     subl.view.run_command('split_selection_by_pattern')

# @emvee_action("delete")
# class Delete(EmveeAction):
#   def run(self, subl, edit, *, delta, by):
#     supportedArgsForBy = ('char', 'word', 'line_from_cursor', 'line', 'full_line')
#     if by not in supportedArgsForBy:
#       raise ValueError('Don\'t know "{}". Supported arguments for "by": {}'.format(by, supportedArgsForBy))

#     delta = int(delta)
#     if delta == 0:
#       return

#     forward = delta > 0
#     amount = abs(delta)

#     #
#     # By char
#     #
#     if by == 'char':
#       sublCommand = 'right_delete' if forward else 'left_delete'

#       subl.view.run_command('add_to_kill_ring', { 'forward': forward })
#       for _ in range(amount):
#         subl.view.run_command(sublCommand)

#     #
#     # By word
#     #
#     elif by == 'word':
#       for _ in range(amount):
#         subl.view.run_command('delete_word', { 'forward': forward })

#     #
#     # By line relative to the cursor
#     #
#     elif by in ('line_from_cursor', 'full_line_from_cursor'):
#       sublCommand = 'right_delete' if forward else 'left_delete'
#       selection = list(subl.view.sel())
#       subl.view.sel().clear()
#       func = getattr(subl.view, 'line' if by == 'line_from_cursor' else 'full_line')
#       for index in range(len(selection)):
#         region = selection[index]
#         row, _ = subl.view.rowcol(region.end())
#         line = func(subl.view.text_point(row + amount - 1, 0))
#         if forward:
#           region = sublime.Region(region.begin(), line.end())
#         else:
#           region = sublime.Region(line.begin(), region.end())
#         selection[index] = region
#       subl.view.sel().add_all(selection)
#       subl.view.run_command('add_to_kill_ring', { 'forward': forward })
#       subl.view.run_command(sublCommand)

#     #
#     # By line
#     #
#     elif by in ('line', 'full_line'):
#       if forward:
#         for _ in range(amount):
#           selection = list(subl.view.sel())
#           subl.view.sel().clear()
#           func = getattr(subl.view, by)
#           for index in range(len(selection)):
#             selection[index] = func(selection[index])
#           subl.view.sel().add_all(selection)
#           subl.view.run_command('add_to_kill_ring', { 'forward': forward })
#         subl.view.run_command('right_delete')
#       else:
#         err('line operations only support positive deltas.')

#     if get_mode(subl.view) == 'select':
#       set_mode(subl.view, NORMAL_MODE)


# @emvee_action("swap_lines")
# class SwapLines(EmveeAction):
#   def __init__(self, amount, *, forward=True):
#     self.amount = amount or 1
#     self.forward = bool(forward)

#   def run(self, subl, edit):
#     cmdStr = 'swap_line_down' if self.forward else 'swap_line_up'
#     for _ in range(self.amount):
#       subl.view.run_command(cmdStr)


# @emvee_action("swap_cursor_with_anchor")
# class SwapCursorWithAnchor(EmveeAction):
#   def run(self, subl, edit, *, side):
#     supportedSides = ('toggle', 'begin', 'end', )
#     if side not in supportedSides:
#       raise ValueError('Don\'t know "{}". Supported arguments for "side": {}'.format(side, supportedSides))

#     selection = list(subl.view.sel())
#     subl.view.sel().clear()

#     if side == 'toggle':
#       selection = [sublime.Region(reg.b, reg.a) for reg in selection]
#     elif side == 'begin':
#       selection = [sublime.Region(reg.end(), reg.begin()) for reg in selection]
#     elif side == 'end':
#       selection = [sublime.Region(reg.begin(), reg.end()) for reg in selection]

#     subl.view.sel().add_all(selection)

# @emvee_action("integer_add")
# class IntegerAdd(EmveeAction):
#   def __init__(self, amount, delta):
#     self.amount = amount or 1
#     self.delta = delta

#   def run(self, subl, edit):
#     for reg in subl.view.sel():
#       if reg.a == reg.b:
#         reg = subl.view.word(reg)
#         try:
#           potentialReg = sublime.Region(reg.begin() - 1, reg.end())
#           word = subl.view.substr(potentialReg)
#           if word.startswith('-'):
#             reg = potentialReg
#         except:
#           pass

#       word = subl.view.substr(reg)
#       try:
#         value = int(word)
#       except:
#         continue
#       value += self.delta
#       newWord = str(value)
#       subl.view.replace(edit, reg, newWord)

# @emvee_action("insert_line")
# class InsertLine(EmveeAction):
#   def __init__(self, amount, above):
#     self.amount = amount or 1
#     self.above = bool(above)

#   def run(self, subl, edit):
#     if self.above:
#       subl.view.run_command('move_to', { 'to': 'hardbol' })
#     else:
#       subl.view.run_command('move_to', { 'to': 'hardeol' })

#     for _ in range(self.amount):
#       subl.view.run_command('insert', { 'characters': '\n' })

#     if self.above:
#       subl.view.run_command('move', { 'by': 'lines', 'forward': False })
#       subl.view.run_command('reindent', { 'force_indent': False })

#     if get_mode(subl.view) != INSERT_MODE:
#       subl.view.run_command('emvee', { 'action': 'enter_insert_mode' })
