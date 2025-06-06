import re
import json


class Edit:
    def __init__(self, word, edit):
        self.word = word
        self.edit = edit
    
    @classmethod
    def create(cls, aligned_src_chars, aligned_tgt_chars):
        """
        Given a pair of aligned words at the character level, generate an edit
        that will turn the src word into the target word

        Args:
            aligned_src_chars (list of str): src word chars
            aligned_tgt_chars (list of str): tgt word chars
        
        Returns:
            edit (str): the edit that would transform the src word to tgt word
        """

        aligned_src_word = "".join(aligned_src_chars)

        if aligned_src_chars == aligned_tgt_chars:
            return cls(aligned_src_word, "K")  # Keep whole word
        
        elif aligned_src_chars == [''] and aligned_tgt_chars != ['']:
            return cls(aligned_src_word, f"I_[{''.join(aligned_tgt_chars)}]")  # Insert whole word

        elif aligned_src_chars != [''] and aligned_tgt_chars == ['']:
            return cls(aligned_src_word, "D")  # Delete whole word

        elif is_merge(aligned_src_chars, aligned_tgt_chars):
            return cls(aligned_src_word, "".join(['K' if c != ' ' else 'M' for c in aligned_src_chars]))  # Merge

        else:
            edit = cls._generate_detailed_edit(aligned_src_chars, aligned_tgt_chars)
            return cls(aligned_src_word, edit)

    @staticmethod
    def _generate_detailed_edit(aligned_src_chars, aligned_tgt_chars):
        """Helper method to generate detailed edits for non-trivial cases."""

        edit = []

        for src_chars, tgt_chars in zip(aligned_src_chars, aligned_tgt_chars):

            if src_chars == tgt_chars: # Keep or mark spaces in src_chars if necessary
                edit.append('S' if src_chars == ' ' else 'K' * len(src_chars))

            elif src_chars == ' ' and tgt_chars == '': # Merge
                edit.append('M')

            elif src_chars == ' ' and tgt_chars != '': # Merge and Insert
                edit.append(f'MI_[{tgt_chars}]')

            elif src_chars != '' and tgt_chars == '': # Delete and mark spaces as merges if necessary
                edit.append(''.join(['D' if c != ' ' else 'M' for c in src_chars]))
    
            elif src_chars == '' and tgt_chars != '': # Insert
                edit.append(f'I_[{tgt_chars}]')

            elif len(src_chars) > len(tgt_chars): # Handle len(src_chars) > len(tgt_chars)
                edit.append(get_edits(src_chars, tgt_chars))

            else: # Replace
                edit.append(Edit._replacments(src_chars, tgt_chars))

        return ''.join(edit)
    
    @staticmethod
    def _replacments(src_chars, tgt_chars):
        """Helper method for replacements"""
        if len(tgt_chars) == 1: # Single char replacement
            return f'R_[{tgt_chars}]'

        elif len(src_chars) == len(tgt_chars): # One-to-one replacement
            edits = []
            for i in range(len(src_chars)):
                if src_chars[i] == ' ':
                    edits.append('M')
                    edits.append(f"I_[{tgt_chars[i]}]")
                else:
                    edits.append(f"R_[{tgt_chars[i]}]")

            return ''.join(edits)

        else:  # Replace each src char and insert remaining tgt chars
            replacements = ''.join([f"R_[{tgt_chars[i]}]" for i in range(len(src_chars))])
            insertions = ''.join([f"I_[{t_char}]" for t_char in tgt_chars[len(src_chars):]])
            return replacements + insertions 

    def apply(self, text):
        pass

    def __repr__(self):
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_json_str(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_dict(self):
        return {'word': self.word, 'edit': self.edit}

    def __len__(self):
        return len(self.edit)

    @classmethod
    def from_json(cls, contents):
        return cls(**contents)



class SubwordEdit:
    def __init__(self, subword, raw_subword, edit):
        self.subword = subword
        self.raw_subword = raw_subword
        self.edit = edit

    def apply(self, subword):
        # Keep
        if self.edit == 'K':
            return subword

        # Appends
        if self.edit.startswith('KA'):
            return self._apply_append(subword, keep=True)

        if self.edit.startswith('DA'):
            return self._apply_append(subword, keep=False)

        # Handle other char-level edits
        _subword = subword.replace('##', '')
        char_edits = re.findall(r'I_\[.*?\]+|A_\[.*?\]+|R_\[.*?\]+|K\*|D\*|.', self.edit)
        edited_subword = self._apply_char_edits(_subword, char_edits)

        # Handle subwords with prefix "##"
        return '##' + edited_subword if '##' in subword else edited_subword

    def _apply_append(self, subword, keep=True):
        """
        Helper method to handle append edits ('KA' or 'DA').
        """
        ops = re.findall(r'A_\[.*?\]+', self.edit)
        inserts = [re.sub(r'A_\[(.*?)\]', r'\1', op) for op in ops]
        return subword + ' ' + ' '.join(inserts) if keep else ''.join(inserts)

    def _apply_char_edits(self, subword, char_edits):
        """
        Apply character-level edits to the word piece (wp).
        """
        edited_subword = ''
        idx = 0

        for i, char_edit in enumerate(char_edits):
            if char_edit == 'K':  # Keep
                edited_subword += subword[idx]
                idx += 1
            
            elif char_edit == 'D':  # Delete
                idx += 1

            elif char_edit.startswith('I'):  # Insert
                edited_subword += re.sub(r'I_\[(.*?)\]', r'\1', char_edit)

            elif char_edit.startswith('A'):  # Append
                edited_subword += (' ' + re.sub(r'A_\[(.*?)\]', r'\1', char_edit) if i
                           else re.sub(r'A_\[(.*?)\]', r'\1', char_edit) + ' ')

            elif char_edit == 'K*':  # Keep and handle remaining edits
                chars_to_keep = self._apply_keep_star(''.join(subword[idx:]), char_edits, i + 1)
                idx += len(chars_to_keep)  # Adjust the index after applying K*
                edited_subword += chars_to_keep

            elif char_edit == 'D*':
                idx += self._apply_delete_star(''.join(subword[idx:]), char_edits, i + 1)

            elif char_edit.startswith('R'):  # Replace
                edited_subword += re.sub(r'R_\[(.*?)\]', r'\1', char_edit)
                idx += 1

        return edited_subword


    def _apply_keep_star(self, subword, char_edits, edit_idx):
        """
        Handle special case of 'K*' if it appears in the beggining of an edit
        """
        remaining_edits = char_edits[edit_idx:]
        inserts = [x for x in remaining_edits if (x.startswith('I') or x.startswith('A'))]

        if len(inserts) == len(remaining_edits):  # if all inserts, add everything
            return ''.join(subword[:])
            
        else: # if not, then add up to the first non-insert edit
            return ''.join(subword[: -(len(remaining_edits) - len(inserts))])


    def _apply_delete_star(self, subword, char_edits, edit_idx):
        remaining_edits = char_edits[edit_idx:]
        inserts_replaces = [x for x in remaining_edits
                            if (x.startswith('I') or x.startswith('A'))]

        if len(inserts_replaces) == len(remaining_edits):  # if all inserts/replaces, delete everything
            return len(subword)
            
        else: # if not, then delete up to the first K edit
            return len(subword[: -(len(remaining_edits) - len(inserts_replaces))])


    def is_applicable(self, subword):
        _subword = subword.replace('##', '')
        char_edits = re.findall(r'I_\[.*?\]+|A_\[.*?\]+|R_\[.*?\]+|K\*|D\*|.', self.edit)
        char_edits_wo_append_merge = [e for e in char_edits if(not e.startswith('A') and
                                      not e.startswith('M') and not e.startswith('I'))]

        if self.edit == 'K' or self.edit.startswith('KA'):
            return True
    

        # if the number of subwords is less than the edits (without A or M), the edit isn't applicable
        if len(_subword) < len(char_edits_wo_append_merge):
            return False

        idx = 0

        for i, edit in enumerate(char_edits_wo_append_merge):
            if edit.startswith('R') or edit in ['K', 'D']:
                idx += 1

            elif edit in ['K*', 'D*']: # we need to advance idx until we reach the edit
                if i == len(char_edits_wo_append_merge) - 1:
                    idx += len(_subword[idx:])
                    break

                idx = len(_subword[: -len(char_edits_wo_append_merge[i + 1:])])
            

        # if we haven't passed over all subwords, the edit isn't applicable
        if idx < len(_subword):
            return False

        return True

    def __repr__(self):
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_json_str(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_dict(self):
        return {'subword': self.subword, 'raw_subword': self.raw_subword, 'edit': self.edit}

    @classmethod
    def from_json(cls, contents):
        return cls(**contents)


class SubwordEdits:
    """
    A wrapper class to create subword edits given an aligned_src_word and its word-level edit
    """
    def __init__(self, subwords, edits):
        self.subwords = subwords
        self.edits = edits

    @classmethod
    def create(cls, aligned_src_word, edit, tokenizer=None):
        """
        Creates subword edits by tokenizing the word-level src alignment
        and project the char-level edit on the subwords

        Args:
            aligned_src_word (str): aligned src
            edit (str): char-level edit
            tokenizer (Tokenizer): extended tokenizer
        """
        if tokenizer:
            raw_subwords, subwords = tokenizer.tokenize(aligned_src_word)
            # Flatten subword lists
            subwords = [wp for sublist in subwords for wp in sublist]
            raw_subwords = [wp for sublist in raw_subwords for wp in sublist]
        else:
            subwords = aligned_src_word.split()
            raw_subwords = subwords

        assert len(subwords) == len(raw_subwords)

        if len(subwords) == 0 and edit.startswith('I'):
            return cls(subwords, [SubwordEdit('', '', compress_edit(edit))])

        if edit == 'K':
            return cls(subwords, [SubwordEdit(subword, raw_subword, 'K')
                                  for subword, raw_subword in zip(subwords, raw_subwords)])

        subword_edits = SubwordEdits._project_edit(subwords, raw_subwords, edit)

        # removing extra spaces from the subwords
        subwords = [wp for wp in subwords if wp != ' ']

        assert len(subwords) == len(subword_edits)
        return cls(subwords, subword_edits)

    @staticmethod
    def _project_edit(subwords, raw_subwords, edit):
        idx = 0
        subword_edits = []
        edit_ops = re.findall(r'I_\[.*?\]+|R_\[.*?\]+|D+|K+|.', edit)
        inserts = [op for op in edit_ops if op.startswith('I_[')]
        replaces = [op for op in edit_ops if op.startswith('R_[')]

        # projecting the edit onto the subwords
        for subword in subwords:
            subword_len = len(subword.replace('##',''))
            subword_edit = ''

            while subword_len > 0:
                if idx >= len(edit):
                    import pdb; pdb.set_trace()

                if edit[idx] == 'S': # Assign current edit to previous subword in case of S
                    subword_edits[-1] += subword_edit
                    subword_edit = ''
                    idx += 1
                    continue

                if edit[idx] == 'I': # inserts
                    op = inserts.pop(0)
                    subword_edit += op
                    idx += len(op)
    
                elif edit[idx] == 'R':
                    op = replaces.pop(0)
                    subword_edit += op
                    idx += len(op)
                    subword_len -= 1

                elif edit[idx] == 'M': # merges
                    # ensure merges happen first
                    if len(subword_edit) != 0:
                        subword_edits[-1] = subword_edits[-1] + subword_edit
                    subword_edit = edit[idx]
                    idx += 1

                else: # keeps/deletes
                    if edit[idx] not in ['K', 'D']:
                        import pdb; pdb.set_trace()
                    subword_edit += edit[idx]
                    idx += 1
                    subword_len -= 1

            subword_edits.append(subword_edit)

        if idx < len(edit):
            subword_edits[-1] = subword_edits[-1] + edit[idx:]


        assert ''.join(subword_edits) == re.sub(r"(?<!\[)S(?!\])", '', edit)

        assert len(subword_edits) == len(subwords) == len(raw_subwords)

        # compressing edits
        subword_edits = [SubwordEdit(subword, raw_subword, compress_edit(edit))
                         for subword, raw_subword, edit in zip(subwords, raw_subwords, subword_edits)]

        return subword_edits

    def __repr__(self):
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_json_str(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_dict(self):
        output = {'subwords': self.subwords,
                  'subword_edits': [subword_edit.edit for subword_edit in self.edits]}
        return output


def get_edits(src_chars, tgt_chars):
    if tgt_chars == '':
        # delete all chars in src_chars
        return 'D' * len(src_chars)

    elif tgt_chars in src_chars:
        # keep what appears in the target and delete the rest
        return ''.join(['D' if c not in tgt_chars else 'K' for c in src_chars])
    
    elif len(src_chars.strip()) == 1 and len(tgt_chars) == 1:
        # replace with tgt and add merge
        return ''.join(['M' if c == ' ' else f'R_[{tgt_chars[0]}]' for c in src_chars])
    
    else:
        edit = ''
        i, j = 0, 0
        # replace source chars with targets whenever possible
        while i < len(src_chars) and j < len(tgt_chars):
            if src_chars[i] != ' ':
                edit += f'R_[{tgt_chars[j]}]'
                j += 1
            elif src_chars[i] == ' ': # merge 
                edit += 'M'
            i += 1

        assert j == len(tgt_chars)

        if i < len(src_chars): # delete the rest of the src chars
            return  edit +  ''.join(['D' * len(src_chars[i:])])
        return edit


def is_merge(aligned_src_chars, aligned_tgt_chars):
    return ''.join([c for c in aligned_src_chars if c != ' ']) == ''.join(aligned_tgt_chars)


def compress_edit(edit):
    grouped_edits = re.findall(r'I_\[.*?\]+|R_\[.*?\]+|A_\[.*?\]+|D+|K+|.', edit)
    grouped_edits = compress_insertions(grouped_edits) # reducing multiple insertions into one
    return ''.join(grouped_edits)


def compress_insertions(edits):
    """Combines consecutive insertions into one."""
    _edits = []
    insertions = ''
    for edit in edits:
        if edit.startswith('I_'):
            insertions += re.sub(r'I_\[(.*?)\]', r'\1', edit)
        else:
            if insertions:
                _edits.append(f'I_[{insertions}]')
                insertions = ''
            _edits.append(edit)

    if insertions:
        _edits.append(f'I_[{insertions}]')
    
    return _edits