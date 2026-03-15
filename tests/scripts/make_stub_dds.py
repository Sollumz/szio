from pathlib import Path


def stub_dds(input_path: Path, output_dir: Path | None = None) -> Path:
    from szio._dds import DdsFile

    dummy_data = b"textureforsziotests"

    tex_data = bytearray(input_path.read_bytes())
    dds = DdsFile.from_buffer(tex_data)

    remaining = len(dds.pixel_data)
    dds.pixel_data[:] = (dummy_data * (remaining // len(dummy_data) + 1))[:remaining]

    if output_dir is None:
        output_path = input_path.with_suffix(".stub.dds")
    else:
        output_path = output_dir / input_path.with_suffix(".stub.dds").name

    output_path.write_bytes(tex_data)
    return output_path


def expand_inputs(patterns: list[str]) -> list[Path]:
    paths = []
    for pattern in patterns:
        matched = list(Path().glob(pattern))
        if not matched:
            raise FileNotFoundError(f"No files matched: {pattern!r}")
        paths.extend(matched)
    return paths


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Stub a DDS texture by replacing pixel data with dummy bytes.")
    parser.add_argument(
        "inputs",
        nargs="+",
        type=str,
        help="Path(s) to input .dds files",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to write stubbed files into (default: alongside each input)",
    )
    args = parser.parse_args()

    try:
        input_paths = expand_inputs(args.inputs)
    except FileNotFoundError as e:
        parser.error(str(e))

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    for input_path in input_paths:
        print(f"{input_path}")
        output = stub_dds(input_path, args.output_dir)
        print(f"  -> {output}")


if __name__ == "__main__":
    main()
