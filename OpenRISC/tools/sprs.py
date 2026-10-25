import csv
import sys

skip = '_'
indent = ' ' * 4

with open(sys.argv[1]) as f:
    next(f)
    sprs = list(csv.reader(f))

cursor = -1
group_cursor = -1
for group, num, name, umode, smode, desc in sprs:
    group = int(group)
    group_start = group << 11

    if group_cursor < group:
        if group_cursor >= 0:
            print('];')
            print('')
        group_cursor = group
        cursor = group_start
        print(f'# SPR Group {group}')
        print(f'define register offset=0x{group_start*4:x} size=4 [')


    if '-' in num:
        first, last = map(int, num.split('-'))
        name = name.split('-')[0].rstrip('0')
    else:
        first = last = int(num)
    first += group_start
    last  += group_start

    # Skip GPRs because SLEIGH can't have duplicate registers
    if name == 'GPR':
        continue

    for i in range(cursor, first):
        print(f'{indent}{skip:<12s}# Not defined')
    for i in range(first, last + 1):
        if last > first:
            this = name + str(i-first)
            print(f'{indent}{this:<12s}# {desc}')
        else:
            print(f'{indent}{name:<12s}# {desc}')
    cursor = last + 1

print('];')
