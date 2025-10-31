from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "region" VARCHAR(2);
        ALTER TABLE "hoyoaccount" ALTER COLUMN "game" TYPE VARCHAR(32) USING "game"::VARCHAR(32);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "region";
        ALTER TABLE "hoyoaccount" ALTER COLUMN "game" TYPE VARCHAR(32) USING "game"::VARCHAR(32);"""


MODELS_STATE = (
    "eJztXetz2rgW/1c8fNqd6XYSyGuZOztjiBN8m0DGdvpIyXiELcA3tsTapint9H+/kt82Bj"
    "vCpgnwpSmyOEf+Hem8dCR+NiysQ9N5f+9Au9HmfjbAbEb+Bs2Nd1wDAQvGLX5H0uyCkem1"
    "z4MGA+nwO3RI09dH8hGMHNcGmks+j4HpQNI0e1LHBjR1j09I1tDpl+fI+HdOP7v2nHbV4R"
    "jMTfplNDfNiLoe96DtwRBC+vpI1bA5t1BMV8caGYaBJjGlCUTQBq5HK/ymNyzVXcy8IXWM"
    "iYjcK2+o5KGGEX0VA7mON/IJ7fTX381mq3XePGqdXZyenJ+fXhxdkL7eeJYfnf/y3snRbG"
    "PmGhjFo5kt3ClGEWvCpOG/STwkn6s3MPFa7Cu0AybQ+vDThl+/8l91HAAeCcVqWpkW3MSZ"
    "Fh24INEUS8qF1kylT1MCi8CPJNb4z3iONPqa3GhumK6BnPe6obn/NFJyDL9YJMgUWyZ5/l"
    "ce9FdJs6xg7hF5+pW+xjvONBz3cY2YKD/62HKcf03a0P/IS90eL/1xy3/+My2+fvdm0KFN"
    "M+y4E9uj4hHoeFKN0TeB46pk1JAuKjrS9UJYWjZhFzB3sYrwc74EwuWXFEAeZyY5XJKnrm"
    "HBTWWhB3Teh/9pJN5LBbqenkp5IlLEW0FW+Nu7lJwueUWgT5pe6yLT+sdZRnYREe6TqPQ4"
    "+pF7GPSFrDijfsoDEerjqrf0pam6eALdqaeNvfU4AtrTM7B1NbWa44mh0WcOdMk6mzissy"
    "JvETKpzmCwVx8kaIJwtjDKObA4XUJPTryfNzlDgsGcTS0VoGl4TnntIBg9vMC8/34rsUjN"
    "mrSCj0GqcMaESmMTjAYIKpj8Ux1ShVPmkRIMOvPQNrRpKQco6Jp0gUDU9BadoIBWWi7FDl"
    "Dz+OT85KJ1dhL5PVFLRe7O9lybb9B2NrCpRWJIkGdaJN0psFdKwwLfVROiiUunb/P0tCz2"
    "hMga7EOPhRD8M+OJ0AVSE1AB6ZpBOj46qhYkQjALEhmAC/3ZXQdQCfL75RJX4z2tsZBJq+"
    "Cj5I2q2C5EnZOW4X8ORuOg8WAb3qRt8P6+cBmXFEFIegf0XYm8ALOy28/gf6uaLnKWy2i6"
    "pGcdabpkPMGo6WgmUa1L3SWIH5KCL9KOaQFVJ51yUiA4kEkHXV/n8XKXv/QSLDZ4jqZQUr"
    "hpqYVhpSc3kYgMIA1uHluGSfCV4fdKa2IC8sKb68n8PJ1PumZrUnGAsRRe6MB+UinOBTAF"
    "ELCYkwQDNl2AsQkB2tSsjAiZdQt7MLhJWZKOmFnm/fvbjkDMsWdWSCfDTa3+GNOJoXppQp"
    "pLL8reT0fHbIn6LJOa52GrWe1EbDWzM3Hq2FuAbYnLm8ftx48fW8BticubxG2rXp6AnkAX"
    "aNNyAW3cO+nnQdKqha2sjl5tTh57ULu//t1af4Vop6IV/PMXs+Lbv6guZZUhcqZGUdaZGd"
    "8E+f3FeIoXmKBU2xyOye89xiqxyBXgnBfaZDjsL9TwOxl10Z4t82yOqe8Xwlt1wq6AbfWx"
    "a4wXpbywRPekGzYmzShqZvTDgkKJ2nJuafpMc2rn9hqW0H+VCbW05LaSUytb2bLSVYWIAq"
    "IXKEfmtFGC/H4kjcgDi0yAQmvz9ZHN2iTpH+xNbfYmua7KGJzMOowsDvXBEirrsJv9OyzM"
    "mr2YrRQ4brYbc4VtaEzQB7jY9n7MRjmQbLqqugKAcvmqHdqQTM9fltKKstYlSf9NZoaTYC"
    "FDe6oIrLzwOkn+zWM1qXFSTTYFSUBzq0j3FQPWuBb6ck/st7lrP8fHidaMGN8hkhVeknjx"
    "ps31MHoCRpuTXWBzEjDMIeoN+h94MXwUfIdr2foQPTw8tLkHiEzoONwDRpB8sPEQKQOlzS"
    "kQ2A6Hx5wyhZbh+QwVyUrD+MmAlRbqp6skI/JMElPg95UKtppprAiflfUuZXQM5WbQvw67"
    "Z/3MNKpE832r1jlIghpTf/OqQifLYqFqU6g9FabhNyg3yDDZj+hRm9t2cQF02MKwtmP6+w"
    "GoDXUILagTDPRClckclC9z2a/QPHXQgR4p9AGpSzlkWOzHTJ7NR6ah1QVpTH0/0NThN0OD"
    "2Rx+dcFBin7dJv+sYpN/tmTy/bcZV3GEaQ1a462cY2pVXNbfyqJlw0k1x+LyoIqJbzGcyo"
    "umBh8FSRZ4uc1hZ4i6JLASZKHNaYg50lnyNPNK2ytOduxZcftLcuhfw0RblBug+cLHMqfr"
    "vT3WnTxJ3scudOKdZfaT5B5EVd5A8DrPkwd7Ih5iL7qOgG7Vq5XNo9cJTrpKofC4fXLuld"
    "mTyszVaE8K0faNyyAOe1IV7UnlVTS8nm2pdTUNte1Mla1q2OxmJsqzJtcipM1avVPKRfPn"
    "dKt5fhZNZ/ohZyY3JEGmie/jIZIE/uZW7d5LktDvfiELYIiUjno3+CRI5OtDdC2qwuc74b"
    "LNnQxRT5bCT6dDdKe0uTOvxyUv3pDvnvs9gk8XlDhho16Kcndw3ye9/x4iodsbqIMr9RMv"
    "0TO1Xh9B+ihcqjHbYzKuDq8ogkTIHDe9xHpI9ZiMSe5KvNLtqV1eIiM5JgP7KF4KA1VWBh"
    "JxOY9Pc1zO9ctUvuVvbpajwkMxTLVRtncJlu/phDdObfH2rTTjw+VbbdbLt5ZE6uXlf4dI"
    "04wPIq1EpJAAu11ZJjkehFiJEH1/3r9x8Bsw63JsctgwCVC2gGkWO+xlnBsWN32F/ffVS9"
    "0YLnPZIQhp3tA3vGWimlMmAHN47BCCwR7tC1A8YpuG+Xx2CEl3StTmFJt1bfKk6O8QboGS"
    "38QnKKqdS3PYPeyeIXzSwaJe+BJMdgjBFeerKjTAO3XC6mVbOmFiKkw6rtnOKXlSInXRcJ"
    "m0dPZm4igvTe+lqOBCrENi+nBY4q0dltCmgE7tWre7szxqrrO4qLbM4oL1xitmvPbwxitt"
    "7rjYUg0LTOorllxisr+1kgEUM5uAYS8oRrgKjZvnMq5iVbMWKG29ymmB86WzEEEQ682m2q"
    "DL8NinYxH0njCTvFiRNmC+kSzJ4M2fjThUrP3eirUlP6qgZK1sjDMlgTKZRbBHrAS2y5Xf"
    "LH3pXTLWCR9O44eHeOe1Xj9yOOi87YPODgQOIVmfKk0xeOMpoFT+scYDz9s57Hx2Uq2VPj"
    "tZchpD5avWWQO2zOV3H4CW70SJv1H5zhdZbnPyzLCByYHRwnGG6HbQbXO30CK2iB5aJoOn"
    "Zf1395KgXoldRRz029zd3Ibc2PB+z26I+LuuKvf4y8GnNsfPsAbMBeGkcc4U6Ph5iMTba1"
    "XpCbxCS7wMa6ISMw2oaTaBTUAZmdgr5XD93/mo7HDqK/1FhY6BSNy1cSpg4UJnnXINAs8o"
    "BCBIdcQ+L33JjwE6OYFq54si8Fl17AK7ziKRfBWdYnqoE2lXUuyD9G3LMcnyIEVmKTKd3U"
    "m5ORmLtHlclHu6o0xstOpYSPzjgH4H/wDI5ntChzsbtx80He5srOvOxmD7n1AOLshQx8Aw"
    "iXNWoNSZC9fXMtyPrZFlCJy5pkGnaJukQswTDHcX85dYOUb79ev/sh0jGA=="
)
