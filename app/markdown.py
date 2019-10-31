def markdown_parse(contents):
    outlines = []
    for line in contents:
        if len(line.strip()) == 0:
            outlines.append('<br>')

        count = 0
        for char in line:
            if char == '#':
                count += 1
            else:
                break

        line = line.strip('#')

        if count > 0:
            line = '<h{0}>{1}</h{0}>'.format(count, line)

        for x in range(line.count('**')):
            if x % 2 == 0:
                line = line.replace('**', '<strong>', 1)
            else:
                line = line.replace('**', '</strong>', 1)

        for x in range(line.count('__')):
            if x % 2 == 0:
                line = line.replace('__', '<strong>', 1)
            else:
                line = line.replace('__', '</strong>', 1)

        for x in range(line.count('*')):
            if x % 2 == 0:
                line = line.replace('*', '<em>', 1)
            else:
                line = line.replace('*', '</em>', 1)

        for x in range(line.count('_')):
            if x % 2 == 0:
                line = line.replace('_', '<em>', 1)
            else:
                line = line.replace('_', '</em>', 1)

        for x in range(line.count('`')):
            if x % 2 == 0:
                line = line.replace('`', '<code>', 1)
            else:
                line = line.replace('`', '</code>', 1)

        outlines.append(line)

    return '\n'.join(outlines)