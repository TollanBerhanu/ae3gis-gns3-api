"""Async telnet helpers shared across CLI tools and the API."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator, Sequence

import telnetlib3


@dataclass(slots=True)
class TelnetSettings:
    host: str
    port: int
    encoding: str = "utf8"
    newline: str = "\r"
    connect_timeout: float = 10.0


class TelnetConsole:
    """Thin wrapper around telnetlib3 reader/writer pair."""

    def __init__(self, settings: TelnetSettings) -> None:
        self._settings = settings
        self._reader: telnetlib3.TelnetReader | None = None
        self._writer: telnetlib3.TelnetWriter | None = None

    async def __aenter__(self) -> "TelnetConsole":
        self._reader, self._writer = await asyncio.wait_for(
            telnetlib3.open_connection(
                host=self._settings.host,
                port=self._settings.port,
                encoding=self._settings.encoding,
            ),
            timeout=self._settings.connect_timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @property
    def reader(self) -> telnetlib3.TelnetReader:
        if self._reader is None:
            raise RuntimeError("Telnet connection not opened")
        return self._reader

    @property
    def writer(self) -> telnetlib3.TelnetWriter:
        if self._writer is None:
            raise RuntimeError("Telnet connection not opened")
        return self._writer

    async def send(self, data: str, *, newline: bool = True) -> None:
        payload = data + (self._settings.newline if newline else "")
        self.writer.write(payload)
        await self.writer.drain()

    async def read(self, *, size: int = 1024, timeout: float = 0.5) -> str:
        try:
            chunk = await asyncio.wait_for(self.reader.read(size), timeout=timeout)
        except asyncio.TimeoutError:
            return ""
        return chunk or ""

    async def read_for(self, duration: float, *, size: int = 1024, poll_interval: float = 0.5) -> str:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + duration
        chunks: list[str] = []
        while loop.time() < deadline:
            remaining = deadline - loop.time()
            chunk = await self.read(size=size, timeout=min(poll_interval, max(remaining, 0.0)))
            if chunk:
                chunks.append(chunk)
        return "".join(chunks)

    async def run_command(self, command: str, *, read_duration: float = 5.0) -> str:
        await self.send(command)
        return await self.read_for(read_duration)

    async def run_command_with_status(
        self,
        command: str,
        *,
        read_duration: float = 5.0,
        sentinel: str = "__EXIT__",
    ) -> tuple[str, int | None]:
        await self.send(f"{command}; printf '{sentinel}%s\\n' $?")
        raw_output = await self.read_for(read_duration)
        exit_code: int | None = None
        output = raw_output
        if sentinel in raw_output:
            prefix, _, suffix = raw_output.rpartition(sentinel)
            output = prefix
            exit_line = suffix.splitlines()[0] if suffix else ""
            try:
                exit_code = int(exit_line.strip())
            except ValueError:
                exit_code = None
        # Consume any trailing prompt characters
        await self.read_for(0.2)
        return output, exit_code

    async def close(self, exit_command: str | None = "exit") -> None:
        if self._writer is None:
            return
        try:
            if exit_command:
                self.writer.write(exit_command + self._settings.newline)
                await self.writer.drain()
        except Exception:
            pass
        try:
            self.writer.close()
            if hasattr(self.writer, "wait_closed"):
                await self.writer.wait_closed()
        except Exception:
            pass
        finally:
            self._reader = None
            self._writer = None


@asynccontextmanager
async def open_console(settings: TelnetSettings) -> AsyncGenerator[TelnetConsole, None]:
    console = TelnetConsole(settings)
    try:
        await console.__aenter__()
        yield console
    finally:
        await console.__aexit__(None, None, None)


async def run_command(host: str, port: int, command: str, *, read_duration: float = 5.0) -> str:
    settings = TelnetSettings(host=host, port=port)
    async with open_console(settings) as console:
        return await console.run_command(command, read_duration=read_duration)


async def run_command_sequence(
    host: str,
    port: int,
    commands: Sequence[tuple[str, float]],
    *,
    inter_command_delay: float = 0.0,
) -> str:
    """Run multiple commands, collecting output for each."""

    settings = TelnetSettings(host=host, port=port)
    output_chunks: list[str] = []
    async with open_console(settings) as console:
        for command, read_duration in commands:
            output_chunks.append(await console.run_command(command, read_duration=read_duration))
            if inter_command_delay > 0:
                await asyncio.sleep(inter_command_delay)
    return "".join(output_chunks)