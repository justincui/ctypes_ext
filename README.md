# ctypes_ext
extension to ctypes
provide an easy way to define complex binary structures. 
provide a wrapper to make an object immutable.

## Demo 
```python
from ctypes import *
from ctypes_ext import *
import pprint

# declare the C struct
S = struct[
        ('a', c_uint16),
        ('', c_uint16),    # padding
        ('d', struct.anon[     # anonymous struct
            ('d0', c_uint8, 1),
            ('d1', c_uint8, 2)
        ]),
        ('e', 2 * struct[       # array of struct
            ('e0', c_uint8, 1),
            ('e1', c_uint8, 2)
        ]),
        ('f', 2 * c_uint32),

        ('c', union.anon[   # anonymous union
            ('cv', c_uint8),
            ('', union.anon[
                ('cs', struct[
                    ('c0', c_uint8, 4),
                    cenum('c0',{0:'Zero', 1: 'One', 2: 'Two', 3: 'Three'}),  # annotate a field with enum
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

# create object with the type S
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

# check accessibility of fields
s.a
s.c; s.cv;    s.cs
s.cs.c0; s.cs.c1
s.d
s.d0; s.d1
s.e[0]
s.e[0].e0; s.e[0].e1
s.f[0]

```

