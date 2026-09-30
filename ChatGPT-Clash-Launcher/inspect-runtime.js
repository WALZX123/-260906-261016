const fs = require('fs');
const root = process.argv[2];
const fd = fs.openSync(root + '/app/resources/app.asar', 'r');
const prefix = Buffer.alloc(16); fs.readSync(fd,prefix,0,16,0);
const headerSize=prefix.readUInt32LE(4), jsonSize=prefix.readUInt32LE(12);
const b=Buffer.alloc(jsonSize); fs.readSync(fd,b,0,jsonSize,16);
const header=JSON.parse(b.toString());
function walk(files,p='') { for(const [name,entry] of Object.entries(files)) {
 const n=p+name;
 if(entry.files) walk(entry.files,n+'/');
 else if(!entry.unpacked && entry.size<30000000 && (n==='package.json'|| /main.*\.js$|\.vite\/build\/.*\.js$/.test(n))) {
  const data=Buffer.alloc(entry.size);fs.readSync(fd,data,0,entry.size,8+headerSize+Number(entry.offset));
  const s=data.toString();
  if(n==='package.json') { const pkg=JSON.parse(s); console.log(JSON.stringify({file:n,name:pkg.name,version:pkg.version,main:pkg.main})); }
  for(const re of [/proxy-server/g,/HTTPS_PROXY/g,/HTTP_PROXY/g,/ALL_PROXY/g,/setProxy\(/g,/proxyUrl/g]) {
   let m,count=0;while((m=re.exec(s)) && count++<6) console.log(JSON.stringify({file:n,term:m[0],context:s.slice(Math.max(0,m.index-150),m.index+240)}));
  }
 }
}}
walk(header.files);fs.closeSync(fd);
