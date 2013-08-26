#!/usr/local/bin/python
import os
import re
import collections
import json
import datetime

path_pisgcfg = './pisg.cfg'
path_irclog = './irclogs'

def cache(func):
    cache_table = {}
    def new_func(*args):
        key = args

        if key in cache_table:
            return cache_table[key]
        value = func(*args)
        cache_table[key] = value
        return value
    return new_func

def openfile(fn):
    if fn.endswith('.bz2'):
        return os.popen('bzcat %s' % fn)
    return open(fn)

def parse_line(line):
    m = re.match(r'^(\d\d:\d\d) <.([^>]+)> (\S+): ', line)
    if m:
        return 'msg_to', m.group(1), m.group(2), m.group(3)

    m = re.match(r'^(\d\d:\d\d) <.([^>]+)> ', line)
    if m:
        return 'msg', m.group(1), m.group(2)

    m = re.match(r'^(\d\d:\d\d) -!- (\S+) .* has joined ', line)
    if m:
        return 'join', m.group(1), m.group(2)

    m = re.match(r'^(\d\d:\d\d)  \* (\S+) ', line)
    if m:
        return 'action', m.group(1), m.group(2)

    return None, None, None

def get_date(fn):
    m = re.search(r'#g0v.tw/(\d{4})/(\d\d)/(\d\d)', fn)
    assert m
    return datetime.date(*map(int, m.group(1, 2, 3)))

normallizer = []

def load_normalizer():
    for line in open(path_pisgcfg):
        m = re.match('<user nick="([^"]+)" alias="([^"]+)"', line)
        if m:
            nick = m.group(1)
            aliases = m.group(2)
            for alias in aliases.split():
                alias = alias.replace('*', '.*')
                normallizer.append(('^'+alias+'$', nick))

@cache
def normalize(nick):
    for rule in normallizer:
        #print rule
        if re.match(rule[0], nick):
            return rule[1]

    nick = re.sub(r'_+$', '', nick)

    return nick

def counting(nicks, threshold):
    bucket = [0]*len(threshold)
    for nick, c in nicks.items():
        for i, t in enumerate(threshold):
            if c >= t:
                bucket[i] += 1
    return bucket

def is_skip_line(line):
    # to ignore some bots
    return re.search("kcwu> .*'s url.*:", line)

def main():
    load_normalizer()

    by_date = []
    threshold = 0, 1, 5, 10, 20, 30, 100
    by_date.append(('threshold', threshold))
    by_date_per_day = []
    by_date_cumu_per_nick = {}
    nicks = collections.defaultdict(int)
    nick_time = {}
    nick_to = {}
    #print threshold
    cumu = {}
    last_date = None
    for root, dirs, files in os.walk(os.path.join(path_irclog, 'FreeNet/#g0v.tw')):
        dirs.sort()
        files.sort()

        for fn in files:
            path = os.path.join(root, fn)
            date = get_date(path)

            if last_date:
                for i in range(date.toordinal() - last_date.toordinal() - 1):
                    for k in cumu.keys():
                        cumu[k].append(cumu[k][-1])
            nicks_one_day = {}

            for line in openfile(path):
                parsed_line = parse_line(line)
                if is_skip_line(line):
                    continue
                cmd, timestr, nick = parsed_line[:3]
                if not nick:
                    continue

                nick = normalize(nick)

                if nick not in nicks:
                    nicks[nick] = 0
                    nick_time[nick] = [0]*24
                    nick_to[nick] = collections.defaultdict(int)
                    cumu[nick] = [str(date)]
                if nick not in nicks_one_day:
                    nicks_one_day[nick] = 0

                if cmd in ('msg_to', 'msg', 'action'):
                    nicks[nick] += 1
                    nicks_one_day[nick] += 1
                    nick_time[nick][int(timestr[:2])] += 1
                    if cmd == 'msg_to':
                        for to in parsed_line[3].split(','):
                            to = normalize(to)
                            if not re.match(r'^[a-zA-Z0-9_^-]+$', to):
                                continue
                            nick_to[nick][to] += 1
                elif cmd == 'join':
                    nicks[nick] += 0
                    nicks_one_day[nick] += 0
                else:
                    assert 0
                #print line
            #print date, len(nicks)
            for k in nicks:
                cumu[k].append(nicks[k])
            by_date.append((str(date), counting(nicks, threshold)))
            by_date_per_day.append((str(date), counting(nicks_one_day, [1])[0]))
            #print date, counting(nicks, threshold)
            last_date = date

    by_nick = []
    for nick, c in sorted(nicks.items(), key=lambda (k,v):v, reverse=True):

        if c <= 20:
            del nick_time[nick]
            del cumu[nick]

        for to, to_c in nick_to[nick].items():
            if to_c == 1:
                del nick_to[nick][to]
        if nick in nick_to and not nick_to[nick]:
            del nick_to[nick]

        if c <= 5:
            continue

        by_nick.append((nick ,c))
        #print nick

    result = dict(by_date=by_date, by_nick=by_nick, by_nick_time=nick_time, by_nick_to=nick_to, by_date_per_day=by_date_per_day,
            by_date_cumu_per_nick=cumu)
    print json.dumps(result)

if __name__ == '__main__':
    main()
