
import typing


__default_block_size__ = 4096  # usual number of a block size in common FS

IOGenerator: typing.TypeAlias = typing.Generator[bytes, None, None]  # a common generator that produce some data
IOProducer: typing.TypeAlias = typing.Union[IOGenerator, typing.Iterable[bytes]]  # a producer that produces some data
# it looks like IOGenerator but more suitable for function arguments
IOProcessor: typing.TypeAlias = typing.Callable[[IOProducer], IOGenerator]  # a processor that consumes some data
# and produces something else

IOAsyncGenerator: typing.TypeAlias = typing.AsyncGenerator[bytes, None]  # a common async-generator that produce
# some data
IOAsyncProcessor: typing.TypeAlias = typing.Callable[[IOAsyncGenerator], IOAsyncGenerator]  # a processor that
# consumes some data from async generators and produces something else
