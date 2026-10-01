// Minimal ZIP writer (stored, no compression) for bundling exported files into one download.

const CRC_TABLE = (() => {
	const table = new Uint32Array(256);
	for (let n = 0; n < 256; n++) {
		let c = n;
		for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
		table[n] = c >>> 0;
	}
	return table;
})();

function crc32(data: Uint8Array): number {
	let crc = 0xffffffff;
	for (let i = 0; i < data.length; i++) crc = CRC_TABLE[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
	return (crc ^ 0xffffffff) >>> 0;
}

function dosDateTime(date: Date): [number, number] {
	const time = (date.getHours() << 11) | (date.getMinutes() << 5) | (date.getSeconds() >> 1);
	const day = ((date.getFullYear() - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
	return [time, day];
}

export function createZip(files: { name: string; text: string }[]): Blob {
	const encoder = new TextEncoder();
	const [time, day] = dosDateTime(new Date());
	const parts: BlobPart[] = [];
	const central: Uint8Array<ArrayBuffer>[] = [];
	let offset = 0;

	for (const file of files) {
		const name = encoder.encode(file.name) as Uint8Array<ArrayBuffer>;
		const data = encoder.encode(file.text) as Uint8Array<ArrayBuffer>;
		const crc = crc32(data);

		const local = new DataView(new ArrayBuffer(30));
		local.setUint32(0, 0x04034b50, true); // local file header
		local.setUint16(4, 20, true); // version needed
		local.setUint16(6, 0x0800, true); // UTF-8 names
		local.setUint16(8, 0, true); // stored
		local.setUint16(10, time, true);
		local.setUint16(12, day, true);
		local.setUint32(14, crc, true);
		local.setUint32(18, data.length, true);
		local.setUint32(22, data.length, true);
		local.setUint16(26, name.length, true);
		parts.push(local.buffer, name, data);

		const entry = new DataView(new ArrayBuffer(46));
		entry.setUint32(0, 0x02014b50, true); // central directory header
		entry.setUint16(4, 20, true);
		entry.setUint16(6, 20, true);
		entry.setUint16(8, 0x0800, true);
		entry.setUint16(10, 0, true);
		entry.setUint16(12, time, true);
		entry.setUint16(14, day, true);
		entry.setUint32(16, crc, true);
		entry.setUint32(20, data.length, true);
		entry.setUint32(24, data.length, true);
		entry.setUint16(28, name.length, true);
		entry.setUint32(42, offset, true);
		const record = new Uint8Array(46 + name.length);
		record.set(new Uint8Array(entry.buffer), 0);
		record.set(name, 46);
		central.push(record);

		offset += 30 + name.length + data.length;
	}

	const centralSize = central.reduce((s, c) => s + c.length, 0);
	const end = new DataView(new ArrayBuffer(22));
	end.setUint32(0, 0x06054b50, true); // end of central directory
	end.setUint16(8, files.length, true);
	end.setUint16(10, files.length, true);
	end.setUint32(12, centralSize, true);
	end.setUint32(16, offset, true);
	return new Blob([...parts, ...central, end.buffer], { type: 'application/zip' });
}
