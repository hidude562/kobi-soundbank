/**
 * kobi-ogg — enough Ogg to cut one note out of a packed program file.
 *
 * An Ogg file is a run of pages; each page header carries the absolute count of samples the stream
 * has completed by its end (the granule position).  Given the file's header pages and the pages
 * that hold a note, `spliceOgg` builds a small, valid Ogg — sequence numbers made contiguous, the
 * last page flagged end-of-stream, CRCs recomputed — that decodeAudioData accepts.
 *
 * Vorbis decoding is deterministic, so the decoded slice is bit-identical to the same span of the
 * whole file.  Where the slice sits is anchored from its end: decoded sample i is absolute sample
 * `granuleEnd - length + i`; a slice that starts at the file's first audio page begins at 0.
 */

const CRC_TABLE = new Uint32Array(256);
for (let i = 0; i < 256; i++) {
  let r = i << 24;
  for (let k = 0; k < 8; k++) r = (r & 0x80000000) ? ((r << 1) ^ 0x04c11db7) : (r << 1);
  CRC_TABLE[i] = r >>> 0;
}

/** Ogg's CRC-32 (polynomial 0x04c11db7, no reflection, zero init) of one page, its CRC field read as zero. */
export function oggCrc(page) {
  let r = 0;
  for (let k = 0; k < page.length; k++) {
    const b = (k >= 22 && k < 26) ? 0 : page[k];
    r = ((r << 8) ^ CRC_TABLE[((r >>> 24) ^ b) & 0xff]) >>> 0;
  }
  return r;
}

/** Page headers in a byte array: [{pos, size, granule, seq, flags}].  Stops at a truncated page. */
export function parsePages(u8) {
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  const pages = [];
  let i = 0;
  while (i + 27 <= u8.length) {
    if (u8[i] !== 0x4f || u8[i + 1] !== 0x67 || u8[i + 2] !== 0x67 || u8[i + 3] !== 0x53) throw new Error(`lost Ogg sync at ${i}`);
    const nseg = u8[i + 26];
    if (i + 27 + nseg > u8.length) break;
    let body = 0;
    for (let s = 0; s < nseg; s++) body += u8[i + 27 + s];
    const size = 27 + nseg + body;
    if (i + size > u8.length) break;
    pages.push({ pos: i, size, granule: Number(dv.getBigInt64(i + 6, true)), seq: dv.getUint32(i + 18, true), flags: u8[i + 5] });
    i += size;
  }
  return pages;
}

/** Header pages + a run of audio pages -> one valid Ogg stream (Uint8Array). */
export function spliceOgg(header, run) {
  const hp = parsePages(header);
  const rp = parsePages(run);
  if (!hp.length || !rp.length) throw new Error('empty header or run');
  const runBytes = rp[rp.length - 1].pos + rp[rp.length - 1].size;      // drop a trailing partial page
  const out = new Uint8Array(header.length + runBytes);
  out.set(header, 0);
  out.set(run.subarray(0, runBytes), header.length);
  const dv = new DataView(out.buffer);
  let seq = hp[hp.length - 1].seq + 1;
  for (let k = 0; k < rp.length; k++) {
    const p = header.length + rp[k].pos;
    dv.setUint32(p + 18, seq++, true);
    if (k === rp.length - 1) out[p + 5] |= 0x04;                          // end of stream
    dv.setUint32(p + 22, oggCrc(out.subarray(p, p + rp[k].size)), true);
  }
  return out;
}

/** Granule position of the last complete page in a run. */
export function lastGranule(run) {
  const rp = parsePages(run);
  return rp.length ? rp[rp.length - 1].granule : null;
}
