const section = ($resource.content || "").match(/\[server_local\]([\s\S]*?)(?=\r?\n\s*\[|$)/i)?.[1] || "";
const tagged = /(?:^|,)\s*tag\s*=[^,]*(?:\uD83C[\uDDE6-\uDDFF]){2}/i;
const content = section.split(/\r?\n/).filter((line) => !/^\s*[;#]/.test(line) && tagged.test(line)).join("\n");
$done({ content });
