import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const root = path.resolve(import.meta.dirname, "..");
const archivePath = path.join(root, "weber-rag", "data", "weber_data.npz");
const outputDir = path.join(root, "docs", "data");

function readZipEntry(archive, wantedName) {
  let eocd = -1;
  for (let offset = archive.length - 22; offset >= Math.max(0, archive.length - 65557); offset -= 1) {
    if (archive.readUInt32LE(offset) === 0x06054b50) {
      eocd = offset;
      break;
    }
  }
  if (eocd < 0) throw new Error("ZIP directory not found");
  const entries = archive.readUInt16LE(eocd + 10);
  let offset = archive.readUInt32LE(eocd + 16);
  for (let index = 0; index < entries; index += 1) {
    if (archive.readUInt32LE(offset) !== 0x02014b50) throw new Error("Invalid ZIP directory");
    const method = archive.readUInt16LE(offset + 10);
    const compressedSize = archive.readUInt32LE(offset + 20);
    const nameLength = archive.readUInt16LE(offset + 28);
    const extraLength = archive.readUInt16LE(offset + 30);
    const commentLength = archive.readUInt16LE(offset + 32);
    const localOffset = archive.readUInt32LE(offset + 42);
    const name = archive.subarray(offset + 46, offset + 46 + nameLength).toString("utf8");
    if (name === wantedName) {
      if (archive.readUInt32LE(localOffset) !== 0x04034b50) throw new Error("Invalid ZIP entry");
      const localNameLength = archive.readUInt16LE(localOffset + 26);
      const localExtraLength = archive.readUInt16LE(localOffset + 28);
      const start = localOffset + 30 + localNameLength + localExtraLength;
      const compressed = archive.subarray(start, start + compressedSize);
      if (method === 0) return compressed;
      if (method === 8) return zlib.inflateRawSync(compressed);
      throw new Error(`Unsupported ZIP compression method ${method}`);
    }
    offset += 46 + nameLength + extraLength + commentLength;
  }
  throw new Error(`ZIP entry not found: ${wantedName}`);
}

function openUnicodeNpy(buffer, label) {
  if (buffer.subarray(0, 6).toString("binary") !== "\x93NUMPY") {
    throw new Error(`Not an NPY file: ${label}`);
  }
  const major = buffer[6];
  const headerLength = major === 1 ? buffer.readUInt16LE(8) : buffer.readUInt32LE(8);
  const dataOffset = (major === 1 ? 10 : 12) + headerLength;
  const header = buffer.subarray(major === 1 ? 10 : 12, dataOffset).toString("ascii");
  const width = Number(header.match(/["']descr["']:\s*["']<U(\d+)["']/)?.[1]);
  const count = Number(header.match(/["']shape["']:\s*\((\d+)/)?.[1]);
  if (!width || !count) throw new Error(`Unsupported NPY header: ${header}`);

  return {
    count,
    read(index) {
      const start = dataOffset + index * width * 4;
      const points = [];
      for (let offset = start; offset < start + width * 4; offset += 4) {
        const codePoint = buffer.readUInt32LE(offset);
        if (codePoint === 0) break;
        points.push(codePoint);
      }
      return String.fromCodePoint(...points);
    },
  };
}

const archive = fs.readFileSync(archivePath);
const documents = openUnicodeNpy(readZipEntry(archive, "chk_documents.npy"), "chk_documents.npy");
const metadatas = openUnicodeNpy(readZipEntry(archive, "chk_metadatas.npy"), "chk_metadatas.npy");
if (documents.count !== metadatas.count) throw new Error("Document/metadata count mismatch");

const allowedPrefixes = ["上海人民-", "上海三联-"];
const books = new Map();

for (let index = 0; index < metadatas.count; index += 1) {
  const metadata = JSON.parse(metadatas.read(index));
  const sourceName = metadata.source_name || "";
  if (!allowedPrefixes.some((prefix) => sourceName.startsWith(prefix))) continue;

  if (!books.has(sourceName)) {
    books.set(sourceName, {
      id: sourceName,
      title: metadata.book_title || metadata.title || sourceName.replace(/^[^-]+-/, ""),
      publisher: metadata.publisher || (sourceName.startsWith("上海人民-") ? "上海人民出版社" : "上海三联书店"),
      author: metadata.author || "马克斯·韦伯",
      year: metadata.year || "",
      chunks: [],
    });
  }

  books.get(sourceName).chunks.push([
    metadata.section_title || metadata.chapter_title || metadata.chapter || "",
    Number(metadata.chunk_index ?? metadata.chunk_no ?? 0),
    documents.read(index),
  ]);
}

const payload = {
  version: 1,
  generatedAt: new Date().toISOString(),
  chunkCount: [...books.values()].reduce((sum, book) => sum + book.chunks.length, 0),
  books: [...books.values()].sort((a, b) => a.publisher.localeCompare(b.publisher, "zh-CN") || a.title.localeCompare(b.title, "zh-CN")),
};

fs.mkdirSync(outputDir, { recursive: true });
const output = path.join(outputDir, "search-data.json");
fs.writeFileSync(output, JSON.stringify(payload));
console.log(`Wrote ${payload.chunkCount} chunks from ${payload.books.length} books to ${output}`);
console.log(`${(fs.statSync(output).size / 1024 / 1024).toFixed(1)} MiB`);
