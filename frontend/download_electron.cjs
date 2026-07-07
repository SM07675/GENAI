const https = require('https');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ver = '33.4.11';
const url = 'https://github.com/electron/electron/releases/download/v' + ver + '/electron-v' + ver + '-win32-x64.zip';
const dest = path.join('node_modules', 'electron', 'electron-win32-x64.zip');
const distDir = path.join('node_modules', 'electron', 'dist');
const pathTxt = path.join('node_modules', 'electron', 'path.txt');

console.log('Downloading Electron v' + ver + '...');
console.log('URL: ' + url);

const file = fs.createWriteStream(dest);
https.get(url, function(res) {
  if (res.statusCode === 302 || res.statusCode === 301) {
    // follow redirect
    https.get(res.headers.location, function(res2) {
      const total = parseInt(res2.headers['content-length'] || 0);
      let got = 0;
      res2.on('data', function(chunk) {
        got += chunk.length;
        if (total) process.stdout.write('\r  ' + Math.round(got/total*100) + '%  (' + Math.round(got/1024/1024) + ' MB)');
      });
      res2.pipe(file);
      file.on('finish', function() {
        file.close(function() { extract(); });
      });
    }).on('error', function(e) { console.error(e.message); });
    return;
  }
  const total = parseInt(res.headers['content-length'] || 0);
  let got = 0;
  res.on('data', function(chunk) {
    got += chunk.length;
    if (total) process.stdout.write('\r  ' + Math.round(got/total*100) + '%  (' + Math.round(got/1024/1024) + ' MB)');
  });
  res.pipe(file);
  file.on('finish', function() {
    file.close(function() { extract(); });
  });
}).on('error', function(e) {
  console.error('Download error: ' + e.message);
  process.exit(1);
});

function extract() {
  console.log('\nExtracting...');
  fs.mkdirSync(distDir, { recursive: true });
  try {
    execSync(
      'powershell -NoProfile -Command "Expand-Archive -LiteralPath \'' + dest + '\' -DestinationPath \'' + distDir + '\' -Force"',
      { stdio: 'inherit' }
    );
    fs.writeFileSync(pathTxt, 'dist/electron.exe');
    console.log('Done! path.txt written: dist/electron.exe');
  } catch(e) {
    console.error('Extraction failed: ' + e.message);
    process.exit(1);
  }
}
