import { Hono } from 'hono';

const app = new Hono();

app.get('/', (c) => c.text('Hello World'));
app.get('/user/:id', (c) => c.json({ id: c.req.param('id') }));

console.log('ready');
if (typeof process !== 'undefined' && process.exit) {
  process.exit(0);
}
