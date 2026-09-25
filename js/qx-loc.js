if (Number($response.statusCode) !== 200) {
  $done(Null);
} else {
  try {
    const o = JSON.parse($response.body);
    const ip = o.query;
    const description = [ip, o.timezone, o.as].filter(Boolean).join("\n");
    $done(ip ? { title: o.city || "", subtitle: o.isp || "", ip, description } : Null);
  } catch {
    $done(Null);
  }
}
