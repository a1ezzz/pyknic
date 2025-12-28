
import typing


__default_block_size__ = 4096  # usual number of a block size in common FS

IOProcessorFunc: typing.TypeAlias = typing.Generator[bytes, None, None]  # a common generator that produce some data
IOAsyncProcessorFunc: typing.TypeAlias = typing.AsyncGenerator[bytes, None]  # a common async-generator that produce
# some data
