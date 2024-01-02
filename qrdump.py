#!/usr/bin/env python3

from itertools import *
import argparse

FORMAT_MASK = [1,0,1,0,1,0,0,0,0,0,1,0,0,1,0]
MODENAMES = {1: 'numeric', 2: 'alphanumeric', 4: 'binary', 8: 'kanji'}
MODEBLOCK = {1: 10, 2: 11, 4: 8}
ALPHANUMERIC = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:'

def mode_length_len(V, mode):
    if 1 <= V <= 9:
        return {1: 10, 2: 9, 4: 8, 8: 8}[mode]
    if 10 <= V <= 26:
        return {1: 12, 2: 11, 4: 16, 8: 10}[mode]
    if 27 <= V <= 40:
        return {1: 14, 2: 13, 4: 16, 8: 12}[mode]
    raise NotImplementedError(f'version {V} not supported')

def decode(block, mode, chars=None):
    if chars is not None and chars <= 0:
        return ''
    if mode == 2:
        chars = 2 if chars is None else min(chars, 2)
        if -1 in block:
            return '?' * chars
        try:
            if chars == 1:
                return ALPHANUMERIC[msb_to_int(block[:6])]
            block = msb_to_int(block)
            return ALPHANUMERIC[block//45] + ALPHANUMERIC[block%45]
        except KeyError:
            return '??'
    raise NotImplementedError(f'mode {mode} not supported')


def msb_to_int(s):
    x = 0
    for y in s:
        if y not in (0, 1):
            raise ValueError
        x = (x << 1) | y
    return x

def lift(f):
    return (lambda *args: -1 if any(x == -1 for x in args) else f(*args))

def mask(maskid, y, x):
    if maskid == 0:
        return int((y+x) % 2 == 0)
    if maskid == 1:
        return int(y % 2 == 0)
    if maskid == 2:
        return int(x % 3 == 0)
    if maskid == 3:
        return int((y+x) % 3 == 0)
    if maskid == 4:
        return int((y//2 + x//3) % 2 == 0)
    if maskid == 5:
        return int((y*x)%2 + (y*x)%3 == 0)
    if maskid == 6:
        return int((y*x + (y*x)%3)%2 == 0)
    if maskid == 7:
        return int((y + x + (y*x)%3)%2 == 0)
    raise NotImplementedError(f'unknown mask id {maskid}')

def from_pgm(s):
    s = s.strip().split('\n' )
    s = [x.strip() for x in s if not x.strip().startswith('#')]
    if s[0] != 'P2':
        raise ValueError('invalid pgm')
    w, h = [int(x) for x in s[1].split()]
    m = int(s[2])
    s = [int(x) for x in ' '.join(s[3:]).strip().split()]
    s = [{0: 1, m: 0}.get(x, -1) for x in s]
    s = list(zip(*([iter(s)] * w), strict=True))
    return s

def str_to_img(s):
    return [[-1 if x == '?' else int(x) for x in r.strip()] for r in s.strip().split('\n') if r]

finder = str_to_img('''
11111110
10000010
10111010
10111010
10111010
10000010
11111110
00000000
''')

align = str_to_img('''
11111
10001
10101
10001
11111
''')

def merge(a, b):
    if a == -1:
        return b
    if b == -1:
        return a
    if a != b:
        raise ValueError
    return a

def is_data(N, y, x):
    if y <= 8 and x <= 8:
        return False
    if y >= N-8 and x <= 8:
        return False
    if x >= N-8 and y <= 8:
        return False
    if y == 6 or x == 6:
        return False
    if y >= N-9 and y <= N-5 and x >= N-9 and x <= N-5:
        return False
    return True

def data_locations(N):
    y = N-1
    x = N-1
    direction = -1
    while x >= 0:
        if y < 0:
            x -= 2
            direction = -direction
            y = 0
            continue
        if y >= N:
            x -= 2
            direction = -direction
            y = N-1
            continue
        if x == 6:
            x = 5
            continue
        if is_data(N, y, x):
            yield (y, x)
        if is_data(N, y, x-1):
            yield (y, x-1)
        y += direction

def qrdump(image):
    '''
    image: NxN array, N = 4*V+17.  each element is light (0) or dark (1) or unknown (-1).
    errors if the known bits are invalid or if not enough format information can be read to even obtain the data/EDC bitstream.

    currently supports only 2 <= V <= 6.
    currently performs no error detection.
    '''
    N = len(image)
    if any(len(r) != N for r in image):
        raise ValueError('not square')
    if N < 17 or (N-17)%4 != 0:
        raise ValueError(f'invalid size {N}')
    V = (N-17)//4
    if not (2 <= V <= 6):
        raise NotImplementedError(f'version {V} is not supported')
    if any(b not in (-1,0,1) for r in image for b in r):
        raise ValueError('invalid contents')

    def assertpixel(y, x, b):
        if b != -1 and image[y][x] not in (-1, b):
            raise ValueError(f'pixel (row={y}, column={x}) should be {b}')

    for y in range(8):
        for x in range(8):
            assertpixel(y, x, finder[y][x])
            assertpixel(N-y-1, x, finder[y][x])
            assertpixel(y, N-x-1, finder[y][x])
    for y in range(5):
        for x in range(5):
            assertpixel(N-y-5, N-x-5, align[y][x])

    for x in range(8, N-8):
        assertpixel(6, x, (x+1)%2)
        assertpixel(x, 6, (x+1)%2)

    assertpixel(N-8, 8, 1)

    format_tl = [image[8][x] for x in range(9) if x != 6] + [image[y][8] for y in range(7, -1, -1) if y != 6]
    format_br = [image[y][8] for y in range(N-1, N-8, -1)] + [image[8][x] for x in range(N-8, N)]
    try:
        format_info = [merge(a, b) for a, b in zip(format_tl, format_br, strict=True)]
    except ValueError:
        raise ValueError(f'format bits do not match (top left = {format_tl}, bottom right = {format_br})')
    format_info = [lift(lambda a, b: a ^ b)(a, b) for a, b in zip(format_info, FORMAT_MASK, strict=True)]
    print(f'format bits: {format_info}')
    level = format_info[0:2]
    maskid = format_info[2:5]
    if -1 in level or -1 in maskid:
        raise ValueError('level or mask unknown')
    level = msb_to_int(level)
    maskid = msb_to_int(maskid)
    print(f'{N=}, {V=}, {level=}, {maskid=}')

    for y, x in data_locations(N):
        print(y, x, image[y][x], mask(maskid, y, x))
    bitstream = [lift(lambda a, b: a ^ b)(image[y][x], mask(maskid, y, x)) for y, x in data_locations(N)]
    print(f'{bitstream=}')
    mode = bitstream[:4]
    bitstream = bitstream[4:]
    if -1 in mode:
        raise ValueError('unknown mode')
    mode = msb_to_int(mode)
    modename = MODENAMES[mode]
    print(f'{mode=} ({modename})')
    LL = mode_length_len(V, mode)
    length = bitstream[:LL]
    bitstream = bitstream[LL:]
    if -1 in length:
        print(f'warning: unknown length {length}')
        length = -1
    else:
        length = msb_to_int(length)
        print(f'{length=}')

    B = MODEBLOCK[mode]
    msg = ''
    for j, i in enumerate(range(0, len(bitstream), B)):
        if i+B > len(bitstream):
            print(f'excess bits: {bitstream[i:]}')
            break
        block = bitstream[i:i+B]
        if False:
            print(f'error-correction block {j}: {block}')
        else:
            decoded = decode(block, mode, None if length == -1 else length - len(msg))
            dm = f', decoded: {decoded}' if decoded else ''
            print(f'block {j}: {block}{dm}')
            msg = msg + decoded
    if length != -1:
        msg = msg[:length]
    print(f'{msg=}')
    
def main():
    p = argparse.ArgumentParser(description='dump info about qr code')
    p.add_argument('file', help='pgm file')
    args = p.parse_args()

    with open(args.file) as f:
        s = f.read()

    img = from_pgm(s)
    qrdump(img)

if __name__ == '__main__':
    main()
