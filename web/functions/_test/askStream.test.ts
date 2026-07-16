import { describe, expect, it } from "vitest";
import { mapAnthropicEvent } from "@watermark/functions/api/_lib/anthropicStream";
import { drainSse, frame } from "@watermark/functions/api/_lib/sse";

describe("drainSse", () => {
  it("pulls complete events and keeps the incomplete tail", () => {
    const { events, rest } = drainSse('event: delta\ndata: {"text":"a"}\n\nevent: delta\ndata: {"te');
    expect(events).toEqual([{ event: "delta", data: '{"text":"a"}' }]);
    expect(rest).toBe('event: delta\ndata: {"te');
  });

  it("defaults the event name and tolerates CRLF", () => {
    const { events } = drainSse("data: hello\r\n\r\n");
    expect(events).toEqual([{ event: "message", data: "hello" }]);
  });

  it("skips frames without a data line (ping/comments)", () => {
    const { events } = drainSse("event: ping\n\n");
    expect(events).toEqual([]);
  });

  it("round-trips with frame()", () => {
    const { events } = drainSse(frame("done", { refused: true }));
    expect(events[0].event).toBe("done");
    expect(JSON.parse(events[0].data)).toEqual({ refused: true });
  });
});

describe("mapAnthropicEvent", () => {
  it("maps a text_delta to a text chunk", () => {
    expect(
      mapAnthropicEvent({
        event: "content_block_delta",
        data: '{"delta":{"type":"text_delta","text":"hi"}}',
      }),
    ).toEqual({
      text: "hi",
    });
  });

  it("ignores non-text deltas", () => {
    expect(
      mapAnthropicEvent({ event: "content_block_delta", data: '{"delta":{"type":"input_json_delta"}}' }),
    ).toBeNull();
  });

  it("lifts input tokens from message_start and output tokens from message_delta", () => {
    expect(
      mapAnthropicEvent({
        event: "message_start",
        data: '{"message":{"usage":{"input_tokens":42,"output_tokens":0}}}',
      }),
    ).toEqual({
      inputTokens: 42,
    });
    expect(mapAnthropicEvent({ event: "message_delta", data: '{"usage":{"output_tokens":17}}' })).toEqual({
      outputTokens: 17,
    });
  });

  it("ignores unrelated events and bad JSON", () => {
    expect(mapAnthropicEvent({ event: "message_stop", data: "{}" })).toBeNull();
    expect(mapAnthropicEvent({ event: "content_block_delta", data: "not json" })).toBeNull();
  });
});
