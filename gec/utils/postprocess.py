from camel_tools.utils.charsets import UNICODE_PUNCT_SYMBOL_CHARSET
import editdistance
import json
import string
import re


puncs = string.punctuation + ''.join(list(UNICODE_PUNCT_SYMBOL_CHARSET)) + '&amp;'

DIGIT_MAPPER={'٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5',
              '٦': '6', '٧': '7', '٨': '8', '٩': '9'}


def norm_digits(string):
    s = ""
    if bool(re.search(r'\d', string)):
        for c in string:
            s += DIGIT_MAPPER.get(c, c)
    return s if s else string


def postprocess(src_sents, preds_sents, verbose=False, gamma=100):

    """
    Compares the src to the prediction and ignore predictions
    that have a big edit distance compared to src.
    """

    # pnx tokenize predictions
    preds_sents = pnx_tokenize(preds_sents)

    assert len(src_sents) == len(preds_sents)

    post_process_out = []
    skipped_sents = []

    pp_sens = []
    for i in range(len(src_sents)):
        src_sent = src_sents[i]
        pred_sent = preds_sents[i]

        dist = editdistance.distance(src_sent, pred_sent)
        if dist >= gamma:
            post_process_out.append(src_sent)
            pp_sens.append(src_sent)
            skipped_sents.append((i, src_sent))
        else:
            post_process_out.append(pred_sent)

    print(f'{len(skipped_sents)} sentences were skipped')
    if verbose:
        for idx, sent in skipped_sents:
            print(f'{idx} :')
            print(f'SRC: {sent}')
            print(f'PRED: {preds_sents[idx]}')
            print()

    return post_process_out


def pnx_tokenize(data):
    pnx_re = re.compile(r'([' + re.escape(puncs) + '])(?!\d)')
    space_re = re.compile(' +')

    pnx_tokenized = []
    for line in data:
        line = line.strip()
        line = pnx_re.sub(r' \1 ', line)
        line = space_re.sub(' ', line)
        line = norm_digits(line)
        line = line.strip()
        pnx_tokenized.append(line)

    return pnx_tokenized


def space_clean(data):
    space_re = re.compile(' +')

    space_cleaned = []
    for line in data:
        line = line.strip()
        line = space_re.sub(' ', line)
        line = line.strip()
        space_cleaned.append(line)

    return space_cleaned


def remove_pnx(data):
    pnx_re = re.compile(r'([' + re.escape(puncs) + '])')
    space_re = re.compile(' +')

    nopnx_data = []
    for line in data:
        line = line.strip()
        line = pnx_re.sub(r'', line)
        line = space_re.sub(' ', line)
        line = line.strip()
        nopnx_data.append(line)

    return nopnx_data


