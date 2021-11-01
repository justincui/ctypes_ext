import inspect, traceback
import pprint
from collections import OrderedDict
from ctypes import _SimpleCData
from collections.abc import Callable, Mapping, Sequence, Iterable
from ctypes import *
from numbers import Number

#################################################################
# func descriptor
class class_or_instance_method(classmethod):
    def __get__(self, instance, type_):
        descr_get = super().__get__ if instance is None else self.__func__.__get__
        return descr_get(instance, type_)

#################################################################
class _OrdDict(OrderedDict):
    def __repr__(self):
        return '{%s}' % ', '.join(["'{}':{}".format(k,v) for k,v in self.items()])

#################################################################
def _cstruct_to_dict(cobj):
    if isinstance(cobj, Array):
        return [_cstruct_to_dict(v) for v in cobj]
    if isinstance(cobj, Union) or isinstance(cobj, Structure):
        result = _OrdDict()
        for f in cobj._fields_:
            fld_name = f[0]
            if not fld_name:
                continue
            if fld_name.startswith('__RSVD_$'):
                if fld_name in cobj._anonymous_:
                    result.update(_cstruct_to_dict(getattr(cobj, fld_name)))
                continue
            result[fld_name] = _cstruct_to_dict(getattr(cobj, fld_name))
        return result
    return cobj

def _cstruct_load_dict(cobj, data={}, **kwargs):
    if kwargs and isinstance(data, Mapping):
        data = dict(data)
        data.update(kwargs)
    return _cstruct_load_dict_internal(cobj, data)

def _cstruct_load_dict_internal(cobj, data, namepath=''):
    if cobj is None:
        return cobj
    if inspect.isclass(cobj): # if cobj is not an instance but a class, we'll create one instance
        cobj = cobj()

    if isinstance(data, Sequence):
        if not isinstance(cobj, Array):
            print("WARNING: when load_dict to ctypes object, {} in c-obj is not an Array and ignored.".format(namepath))
            for line in traceback.format_stack():
                if 'in _cstruct_load_dict' in line:
                    break
                print(line.strip())
        else:
            for i,v in enumerate(data):
                if isinstance(v, Number):
                    cobj[i] = v
                else:
                    _cstruct_load_dict(cobj[i], v, namepath=namepath + '[' + str(i) + ']')
    elif isinstance(data, Mapping):
        for k,v in data.items():
            if isinstance(v, Number):
                if hasattr(cobj, k):
                    setattr(cobj, k, v)
                else:
                    print("WARNING: when load_dict to ctypes object, <cobj@{}>{}.{} not exist and setting this field to {}({}) is ignored.".format(addressof(cobj), namepath, k, v, hex(v)))
                    for line in traceback.format_stack():
                        if 'in _cstruct_load_dict' in line:
                            break
                        print(line.strip())

            else:
                _cstruct_load_dict(getattr(cobj, k, None), v, namepath=namepath + '.' + k)
    else:
        cobj.value = data  # c simple data
    return cobj

##########################################################################################################################

def _cstruct_to_loadable_code(cobj, wrap=True):
    strs = []

    for name, *typedef in cobj.__class__._fields_:
        if not name:  # skip empty names
            continue

        fld_obj = getattr(cobj, name)

        if name.startswith('__RSVD_$'): # unnamed fields in struct/union
            if name in cobj._anonymous_:
                strs.append(_cstruct_to_loadable_code(fld_obj, wrap=False))
            continue

        if isinstance(fld_obj, Array):
            if len(fld_obj) == 0:  # skip empty array
                continue
            if issubclass(fld_obj._type_, _SimpleCData):
                if(len(fld_obj)<=10):
                    fld_str = '[' + ', '.join([hex(o) for o in fld_obj]) + ']'
                else:
                    fld_str = '[' + ''.join([
                        ', '.join(hex(n) for n in fld_obj[i:i + 10])+(',     #### {}\n'.format(i+len(fld_obj[i:i+10])))
                            for i in range(0, len(fld_obj), 10)
                     ]) + ']'
            else:
                fld_str = '[\n\t' + ',\n\t'.join(
                    [_cstruct_to_loadable_code(o).replace('\n', '\n\t') for o in fld_obj]
                ) + '\n]'
        elif isinstance(fld_obj, Number):
            fld_str = hex(fld_obj)
        else:
            fld_str = _cstruct_to_loadable_code(fld_obj)

        s = "\t'{}': {},".format(name, fld_str)
        s = s.replace('\n', '\n\t')
        strs.append(s)

    if len(strs) <= 1:
        return '{' + ''.join(strs).strip() + '}' if wrap else ''.join(strs)
    else:
        return '{\n' + '\n'.join(strs) + '\n}' if wrap else '\n'.join(strs)

##########################################################################################################################

def _cstruct_str(cobj, value_enum_maps):
    strs = []

    for name, *typedef in cobj.__class__._fields_:
        if not name:  # skip empty names
            continue
        bits = ':{}'.format(typedef[1]) if len(typedef) > 1 else ''
        typestr = typedef[0].__name__ + bits
        display_name = '' if name and name.startswith('__RSVD_$') else name  # check_fields() converts an emtpy field name into __RSVD_$digits'
        warning = ''

        fld_obj = getattr(cobj, name)
        if isinstance(fld_obj, Array):
            if issubclass(fld_obj._type_, _SimpleCData):
                if(len(fld_obj)<=10):
                    fld_str = '[' + ', '.join([hex(o) for o in fld_obj]) + ']'
                else:
                    fld_str = '[' + ''.join([
                        ', '.join(hex(n) for n in fld_obj[i:i + 10])+(',     #### {}\n'.format(i+len(fld_obj[i:i+10])))
                            for i in range(0, len(fld_obj), 10)
                     ]) + ']'
            else:
                fld_str = '[\n\t' + '\n\t'.join(
                    [str(i)+'=> '+str(o).replace('\n', '\n\t') for i,o in enumerate(fld_obj)]
                ) + '\n]'
        elif isinstance(fld_obj, Number):
            fld_str = hex(fld_obj)
            if not display_name:
                warning = '# WARNING: non-zero RSVD field' if fld_obj != 0 else ''
            elif display_name in value_enum_maps:
                mapper = value_enum_maps[display_name]
                if isinstance(mapper, Mapping):
                    enum_str = str(mapper.get(fld_obj, '_UNKNOWN_'))
                elif isinstance(mapper, Callable):
                    enum_str = str(mapper(fld_obj))
                else:
                    enum_str = '_NOT_MAPPED_'
                fld_str += ' <'+enum_str+'>'
        else:
            fld_str = str(fld_obj)

        s = ' \t{} <{}> = {}  {}'.format(display_name, typestr, fld_str, warning)
        s = s.replace('\n', '\n\t')
        strs.append(s)

    if len(strs)<=1:
        return cobj.__class__.__name__ + '{' + ''.join(strs) + '}'
    else:
        return cobj.__class__.__name__ + '{\n' + '\n'.join(strs) + '\n}'


########################################################################################################################
class __CENUM:
    def __init__(self, field, value_map_or_mapfunc, debug_info):
        field = field.strip(' \t.')
        self.field = field

        if isinstance(value_map_or_mapfunc, Callable) or isinstance(value_map_or_mapfunc, Mapping):
            self.enum_map = value_map_or_mapfunc
        else:
            raise ValueError('cenum() needs value mapping dict or func')

        self.debug_info = debug_info


def cenum(field, value_map_or_mapfunc):
    caller = inspect.getframeinfo(inspect.stack()[1][0])
    return __CENUM(field, value_map_or_mapfunc, "cenum('{}', {}) at {}[line {}]"
                   .format(field, value_map_or_mapfunc, caller.filename, caller.lineno))


########################################################################################################################
class __CINIT:
    def __init__(self, field, value, debug_info):
        field = field.strip(' \t.')
        self.field = tuple(field.split('.'))
        self.value = value
        self.debug_info = debug_info


def cinit(field, value):
    caller = inspect.getframeinfo(inspect.stack()[1][0])
    return __CINIT(field, value, "cinit('{}', {}) at {}[line {}]"
                   .format(field, value, caller.filename, caller.lineno))


########################################################################################################################
def init_fields(obj):
    if hasattr(obj, '_fields_') and isinstance(obj._fields_, Iterable):
        for f in obj._fields_:
            member = getattr(obj, f[0])
            if hasattr(member, '__init__'):
                member.__init__()


__dummy_cnt = 0
def _cstruct_fields_check(fields):
    _cinits = []
    _cenums = {}
    _fields = []
    for o in fields:
        if isinstance(o, __CINIT):
            _cinits.append(o)
        elif isinstance(o, __CENUM):
            _cenums[o.field] = o.enum_map
        else:
            _fields.append(o)

    fields = _fields
    global __dummy_cnt
    names = set()

    for i, (nm, *tp) in enumerate(fields):
        nm = nm.strip()
        if not nm:
            nm = '__RSVD_${}'.format(__dummy_cnt)
            __dummy_cnt += 1
            fields[i] = (nm, tp[0]) if len(tp) == 1 else (nm, tp[0], tp[1])
        if nm in names:
            raise SyntaxError('field name in union/struct conflicts:{}'.format(nm))
        names.add(nm)

    return fields, _cinits, _cenums


class _ANONYMOUS:
    pass


def _cstruct(fields, is_union=False, anonymous=False):
    fields, _cinits, _cenums = _cstruct_fields_check(fields)

    base_ctype = Union if is_union else Structure
    clz_name = 'union' if is_union else 'struct'
    if anonymous:
        clz_name += '.anon'

    bases = (base_ctype, _ANONYMOUS) if anonymous else (base_ctype,)

    class clz(*bases):
        _pack_ = 1
        _fields_ = fields
        _anonymous_ = [name for name, *t in fields if issubclass(t[0], _ANONYMOUS)]

        def __str__(self):
            return _cstruct_str(self, value_enum_maps=_cenums)

        def __repr__(self):
            return _cstruct_str(self, value_enum_maps=_cenums)

        def __init__(self):
            init_fields(self)
            for ci in _cinits:
                o = self
                try:
                    for k in ci.field[:-1]:
                        o = getattr(o, k)
                    setattr(o, ci.field[-1], ci.value)
                except AttributeError as e:
                    raise ValueError(ci.debug_info) from e

    clz.__name__ = clz_name
    clz.to_dict = _cstruct_to_dict
    clz.pretty_dict = _cstruct_to_loadable_code
    clz.load_dict = class_or_instance_method(_cstruct_load_dict)
    return clz


# wrapper to make function call _union([...]) into union[...]
union = type('union()', tuple(), {'__getitem__':lambda _,x: _cstruct(list(x), is_union=True, anonymous=False)})()
union.anon = type('union.anon', tuple(),{'__getitem__':lambda _,x: _cstruct(list(x), is_union=True, anonymous=True)})()

struct = type('struct()', tuple(), {'__getitem__':lambda _,x: _cstruct(list(x), is_union=False, anonymous=False)})()
struct.anon = type('struct.anon', tuple(), {'__getitem__':lambda _,x: _cstruct(list(x), is_union=False, anonymous=True)})()


#################################################################
def default_index(cls, fld_name):
    setattr(cls, '__getitem__', lambda obj_of_cls, idx: getattr(obj_of_cls, fld_name).__getitem__(idx))
    setattr(cls, '__setitem__', lambda obj_of_cls, idx, value: getattr(obj_of_cls, fld_name).__setitem__(idx,value))

#################################################################
def print_bytes(msg):
    data = bytearray(msg)
    s = "|".join([" ".join('{:02x}'.format(c) for c in data[x:x+4]) for x in range(0, len(data), 4)])
    print(s)

#################################################################
def fill_head_body(target_obj, header, body_bytes):
    if header:
        memmove(addressof(target_obj), addressof(header), sizeof(header))
    if body_bytes:
        if header is None:
            header = target_obj.header
        size = min(sizeof(target_obj)-sizeof(header), len(body_bytes))
        memmove(addressof(target_obj) + sizeof(header), bytes(body_bytes), size)

#################################################################
if __name__ == '__main__':
    S = struct[
        ('a', c_uint16),
        ('', c_uint16),
        ('d', struct.anon[
            ('d0', c_uint8, 1),
            ('d1', c_uint8, 2)
        ]),
        ('e', 2 * struct[
            ('e0', c_uint8, 1),
            ('e1', c_uint8, 2)
        ]),
        ('f', 2 * c_uint32),

        ('c', union.anon[
            ('cv', c_uint8),
            ('', union.anon[
                ('cs', struct[
                    ('c0', c_uint8, 4),
                    cenum('c0',{0:'Zero', 1: 'One', 2: 'Two', 3: 'Three'}),
                    ('c1', c_uint8, 4)
                ]),
                ('cs1', struct[
                    ('c0', c_uint8, 4),
                    ('c1', c_uint8, 4)
                ]),
            ]),
        ]),
        cinit('a', 1),
        cinit('c.cs.c0', 2),
        cinit('d1', 3),
    ]

    s=S()
    print("---------------test1--------------------")
    print(s)
    print("---------------test2--------------------")
    s.f[0]=123
    s.f[1]=456
    s.e[0].e0=1
    s.e[0].e1=2
    s.e[1].e1=3

    print(str(s))
    print("---------------test3--------------------")
    d1=s.to_dict()
    pprint.pprint(d1)
    print("-----------------------------------")
    s2=S()
    s2.load_dict(d1, invalid_field=0xabcd)
    print(s2)
    assert(str(s)==str(s2))
    print("-----------------------------------")
    d1['d']['invalid_field'] = 0x12345
    s3=S.load_dict(d1)
    print(s3)
    assert(str(s) == str(s3))
    print("______________________________________")
    print(_cstruct_to_loadable_code(s))
    print("-----------------------------------")
    # check accessibility of fields
    s.a
    s.c; s.cv;    s.cs
    s.cs.c0; s.cs.c1
    s.d
    s.d0; s.d1
    s.e[0]
    s.e[0].e0; s.e[0].e1
    s.f[0]

