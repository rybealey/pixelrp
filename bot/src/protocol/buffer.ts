export class BinaryWriter {
  private parts: Buffer[] = [];

  writeInt(n: number): this {
    const b = Buffer.alloc(4);
    b.writeInt32BE(n);
    this.parts.push(b);
    return this;
  }

  writeShort(n: number): this {
    const b = Buffer.alloc(2);
    b.writeUInt16BE(n);
    this.parts.push(b);
    return this;
  }

  writeString(s: string): this {
    const utf8 = Buffer.from(s, "utf8");
    this.writeShort(utf8.length);
    this.parts.push(utf8);
    return this;
  }

  writeBool(v: boolean): this {
    this.parts.push(Buffer.from([v ? 1 : 0]));
    return this;
  }

  toBuffer(): Buffer {
    return Buffer.concat(this.parts);
  }
}

export class BinaryReader {
  private offset = 0;
  constructor(private buf: Buffer) {}

  private need(n: number) {
    if (this.offset + n > this.buf.length)
      throw new RangeError(`read past end (need ${n} at ${this.offset}/${this.buf.length})`);
  }

  readInt(): number {
    this.need(4);
    const v = this.buf.readInt32BE(this.offset);
    this.offset += 4;
    return v;
  }

  readShort(): number {
    this.need(2);
    const v = this.buf.readUInt16BE(this.offset);
    this.offset += 2;
    return v;
  }

  readString(): string {
    const len = this.readShort();
    this.need(len);
    const v = this.buf.toString("utf8", this.offset, this.offset + len);
    this.offset += len;
    return v;
  }

  readBool(): boolean {
    this.need(1);
    return this.buf[this.offset++] === 1;
  }

  remaining(): number {
    return this.buf.length - this.offset;
  }
}
