const fs = require('node:fs');
fs.mkdirSync('dist', {recursive:true});
for (const name of ['index.html','style.css','app.js']) fs.copyFileSync(name, 'dist/' + name);
console.log('Static site built');
