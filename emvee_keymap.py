import json

def get_keymap(): return [
  define(['f1'], [ ], None, context=[
      { 'key': 'emvee_display_current_mode' },
      { 'key': 'emvee_early_out' },
    ]),

  comment('',
          'Escape',
          ''),
  define(['escape'], ['NORMAL'], None, context=[
    { 'key': 'setting.is_widget', 'operand': False },
    # { 'key': 'panel_visible', 'operator': 'equal', 'operand': False },
    # { 'key': 'overlay_visible', 'operator': 'equal', 'operand': False },
    # { 'key': 'popup_visible', 'operator': 'equal', 'operand': False },
    { 'key': 'auto_complete_visible', 'operator': 'equal', 'operand': False },
    { 'key': 'emvee_clear_state' },
    { 'key': 'emvee_early_out' },
  ]),
  define(['escape'], ['INSERT', 'SELECT'], 'enter_normal_mode', context=[
    { 'key': 'setting.is_widget', 'operand': False },
    # { 'key': 'panel_visible', 'operator': 'equal', 'operand': False },
    # { 'key': 'overlay_visible', 'operator': 'equal', 'operand': False },
    # { 'key': 'popup_visible', 'operator': 'equal', 'operand': False },
    { 'key': 'auto_complete_visible', 'operator': 'equal', 'operand': False },
  ]),

  comment('',
          'Digits',
          ''),
  define(['0'], ['NORMAL', 'SELECT'], 'push_digit', { 'digit': 0 }),
  define(['1'], ['NORMAL', 'SELECT'], 'push_digit', { 'digit': 1 }),
  define(['2'], ['NORMAL', 'SELECT'], 'push_digit', { 'digit': 2 }),
  define(['3'], ['NORMAL', 'SELECT'], 'push_digit', { 'digit': 3 }),
  define(['4'], ['NORMAL', 'SELECT'], 'push_digit', { 'digit': 4 }),
  define(['5'], ['NORMAL', 'SELECT'], 'push_digit', { 'digit': 5 }),
  define(['6'], ['NORMAL', 'SELECT'], 'push_digit', { 'digit': 6 }),
  define(['7'], ['NORMAL', 'SELECT'], 'push_digit', { 'digit': 7 }),
  define(['8'], ['NORMAL', 'SELECT'], 'push_digit', { 'digit': 8 }),
  define(['9'], ['NORMAL', 'SELECT'], 'push_digit', { 'digit': 9 }),

  comment('',
          'View controls',
          ''),
  define(['z', 'j'], ['NORMAL', 'SELECT'], 'scroll', { 'delta_screens_x': -0.0, 'delta_screens_y': -0.2 }),
  define(['z', 'k'], ['NORMAL', 'SELECT'], 'scroll', { 'delta_screens_x': -0.0, 'delta_screens_y': +0.2 }),
  define(['z', 'h'], ['NORMAL', 'SELECT'], 'scroll', { 'delta_screens_x': -0.5, 'delta_screens_y': -0.0 }),
  define(['z', 'l'], ['NORMAL', 'SELECT'], 'scroll', { 'delta_screens_x': +0.5, 'delta_screens_y': -0.0 }),
  define(['z', 'z'], ['NORMAL', 'SELECT'], 'scroll', { 'center_cursor': True }),

  comment('',
          'Enter INSERT mode',
          ''),
  define(['i'], ['NORMAL', 'SELECT'], 'enter_insert_mode', { 'location': 'current' }),
  define(['I'], ['NORMAL', 'SELECT'], 'enter_insert_mode', { 'location': 'line_limit' }),
  define(['a'], ['NORMAL', 'SELECT'], 'enter_insert_mode', { 'location': 'current', 'append': True }),
  define(['A'], ['NORMAL', 'SELECT'], 'enter_insert_mode', { 'location': 'line_limit', 'append': True }),

  comment('',
          'Enter SELECT mode',
          ''),
  define(['v'], ['NORMAL'], 'select', { 'mode': 'char' }),
  define(['v', 'v'], ['NORMAL'], 'select', { 'mode': 'block' }),
  define(['V'], ['NORMAL', 'SELECT'], 'select', { 'mode': 'line' }),

  comment('',
          'Movement',
          ''),
  define(['h'], ['NORMAL'], 'move_by_char', { 'forward': False, 'stay_in_line': True }),
  define(['l'], ['NORMAL'], 'move_by_char', { 'forward': True, 'stay_in_line': True }),
  define(['j'], ['NORMAL'], 'move_by_line', { 'forward': True }),
  define(['k'], ['NORMAL'], 'move_by_line', { 'forward': False }),
  define(['h'], ['SELECT'], 'move_by_char', { 'forward': False, 'stay_in_line': True, 'extend': True }),
  define(['l'], ['SELECT'], 'move_by_char', { 'forward': True, 'stay_in_line': True, 'extend': True }),
  define(['j'], ['SELECT'], 'move_by_line', { 'forward': True, 'extend': True }),
  define(['k'], ['SELECT'], 'move_by_line', { 'forward': False, 'extend': True }),
  define(['alt+shift+j'], ['NORMAL'], 'select_lines', { 'forward': True }, builtin=True),
  define(['alt+shift+k'], ['NORMAL'], 'select_lines', { 'forward': False }, builtin=True),
  define(['g', 'h'], ['NORMAL'], 'move_to_line_limit', { 'forward': False }),
  define(['g', 'l'], ['NORMAL'], 'move_to_line_limit', { 'forward': True }),
  define(['g', 'h'], ['SELECT'], 'move_to_line_limit', { 'forward': False, 'extend': True }),
  define(['g', 'l'], ['SELECT'], 'move_to_line_limit', { 'forward': True, 'extend': True }),
  define(['alt+h'], ['NORMAL'], 'move_to_line_limit', { 'forward': False }),
  define(['alt+l'], ['NORMAL'], 'move_to_line_limit', { 'forward': True }),
  define(['alt+shift+h'], ['NORMAL'], 'move_to_line_limit', { 'forward': False, 'extend': True }),
  define(['alt+shift+l'], ['NORMAL'], 'move_to_line_limit', { 'forward': True, 'extend': True }),
  define(['w'], ['NORMAL'], 'move_by_word_begin', { 'forward': True }),
  define(['w'], ['SELECT'], 'move_by_word_begin', { 'forward': True, 'extend': True }),
  define(['e'], ['NORMAL'], 'move_by_word_end', { 'forward': True }),
  define(['e'], ['SELECT'], 'move_by_word_end', { 'forward': True, 'extend': True }),
  define(['b'], ['NORMAL'], 'move_by_word_begin', { 'forward': False }),
  define(['b'], ['SELECT'], 'move_by_word_begin', { 'forward': False, 'extend': True }),

  comment('Move cursor to previous or next empty line'),
  define(['['], ['NORMAL', 'SELECT'], 'move_by_empty_line', { 'forward': False }),
  define([']'], ['NORMAL', 'SELECT'], 'move_by_empty_line', { 'forward': True }),
  define(['{'], ['NORMAL', 'SELECT'], 'move_by_empty_line', { 'forward': False, 'select': True }),
  define(['}'], ['NORMAL', 'SELECT'], 'move_by_empty_line', { 'forward': True, 'select': True }),

  define(['alt+k'], ['NORMAL', 'SELECT'], 'swap_line_up', builtin=True),
  define(['alt+j'], ['NORMAL', 'SELECT'], 'swap_line_down', builtin=True),

  define([' '], ['NORMAL', 'SELECT'], 'flip_cursors_within_selections'),

  define(['d'], ['NORMAL', 'SELECT'], 'right_delete', builtin=True),
  define(['D'], ['NORMAL', 'SELECT'], 'delete_to_eol'),
  define(['ctrl+D'], ['NORMAL', 'SELECT'], 'delete_line'),

  define(['o'], ['NORMAL', 'SELECT'], 'insert_line', { 'above': False }),
  define(['O'], ['NORMAL', 'SELECT'], 'insert_line', { 'above': True }),

  define(['s'], ['NORMAL', 'SELECT'], 'split_selection', { 'forward': True }),
  define(['alt+s'], ['NORMAL', 'SELECT'], 'split_selection', { 'forward': False }),

  define(['f'],           ['NORMAL', 'SELECT'], 'find_char', { 'forward': True, 'extend': False }),
  define(['shift+f'],     ['NORMAL', 'SELECT'], 'find_char', { 'forward': True, 'extend': True }),
  # TODO Why do these exist? Do I even use these? They're the same as the two above.
  define(['alt+f'],       ['NORMAL', 'SELECT'], 'find_char', { 'forward': True, 'extend': False }),
  define(['alt+shift+f'], ['NORMAL', 'SELECT'], 'find_char', { 'forward': True, 'extend': True }),

  comment('Move cursor between matching parens, brackets, and braces.'),
  define(['m'], ['NORMAL', 'SELECT'], 'move_to', { 'to': 'brackets', 'extend': False }, builtin=True),
  define(['M'], ['NORMAL', 'SELECT'], 'move_to', { 'to': 'brackets', 'extend': True }, builtin=True),

  comment('Integer manipulation'),
  define(['='], ['NORMAL', 'SELECT'], 'integer_add', { 'delta': 1 }),
  define(['alt+='], ['NORMAL', 'SELECT'], 'integer_add', { 'delta': -1 }),

  comment('Undo, redo'),
  define(['u'],     ['NORMAL', 'SELECT'], 'undo', builtin=True),
  define(['r'],     ['NORMAL', 'SELECT'], 'redo', builtin=True),
  define(['alt+u'], ['NORMAL', 'SELECT'], 'soft_undo', builtin=True),
  define(['alt+r'], ['NORMAL', 'SELECT'], 'soft_redo', builtin=True),

  comment('Find/Search'),
  define(['/'], ['NORMAL', 'SELECT'], 'show_panel', {'panel': 'incremental_find', 'reverse': False }, builtin=True),
  define(['?'], ['NORMAL', 'SELECT'], 'show_panel', {'panel': 'incremental_find', 'reverse': True }, builtin=True),
  define(['n'], ['NORMAL', 'SELECT'], 'find_next', builtin=True),
  define(['N'], ['NORMAL', 'SELECT'], 'find_prev', builtin=True),
  define(['alt+n'], ['NORMAL', 'SELECT'], 'find_all_under', builtin=True),
]

def define(keys, modes, action, args=None, *, builtin=False, next_mode=None, context=[]):
  def result_maker(newline):
    nonlocal keys, modes, action, args, builtin, next_mode, context
    context = context or []
    result = '{ '
    result += '"keys": {:16}'.format(json.dumps(keys))
    command = 'emvee'
    if builtin:
      command = action
    elif action:
      if not args:
        args = dict()
      args['action'] = action
    result += ', "command": {:20}'.format(json.dumps(command))
    if args:
      result += ', "args": {}'.format(json.dumps(args))
    if modes:
      context.insert(0, { "key": "emvee_current_mode", "operand": ','.join(modes) })
    if next_mode:
      context.append({ "key": "emvee_set_next_mode", 'operand': next_mode})
    if len(context) == 1:
      result += ', "context": {} '.format(json.dumps(context))
    if len(context) > 1:
      result += ', "context": ['
      indent(1)
      context_prefix = ''
      for line in context:
        result += context_prefix + newline + indentation() + json.dumps(line)
        context_prefix = ','
      indent(-1)
      result += '{}{}]'.format(newline, indentation())
    result += '},'
    return result
  return result_maker

def comment(text):
  def result_maker(newline):
    nonlocal text
    return '{}{}// {}'.format(newline, indentation(), text)
  return result_maker

def comment(*text_lines):
  def result_maker(newline):
    nonlocal text_lines
    indent = newline + indentation()
    return ''.join('{}// {}'.format(indent, x).rstrip() for x in text_lines)
  return result_maker

_indentation = '  '
_indent_level = 0
def indentation():
  global _indent_level
  global _indentation
  return _indent_level*_indentation
def indent(amount):
  global _indent_level
  _indent_level += amount

if __name__ == '__main__':
  from sys import stdout

  newline = '\n'
  result = '['
  indent(1)
  for entry in get_keymap():
    result += newline + indentation() + entry(newline)
  indent(-1)
  result += newline + ']'

  print(result, file=stdout)
