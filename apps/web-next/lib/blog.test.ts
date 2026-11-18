import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { faqPairs } from "./blog.ts";

const POST = `## Perguntas frequentes

### O Bonsai 2 27B é bom em português?
A média de ARC-Challenge, HellaSwag e TruthfulQA foi de 54,6%.
Esses testes não são específicos para português.

### Roda no Ollama?
Não foi testado.

## Fontes

- https://example.test
`;

describe("faqPairs", () => {
  it("reads the questions and answers of the FAQ section", () => {
    const pairs = faqPairs(POST);
    assert.equal(pairs.length, 2);
    assert.equal(pairs[0].question, "O Bonsai 2 27B é bom em português?");
    assert.match(pairs[0].answer, /54,6%/);
    assert.match(pairs[0].answer, /não são específicos/);
    assert.equal(pairs[1].question, "Roda no Ollama?");
    assert.equal(pairs[1].answer, "Não foi testado.");
  });

  it("stops at the next section", () => {
    const pairs = faqPairs(POST);
    assert.ok(!pairs.some((pair) => pair.question.includes("Fontes")));
    assert.ok(!pairs.some((pair) => pair.answer.includes("example.test")));
  });

  it("returns nothing when the post has no FAQ", () => {
    assert.deepEqual(faqPairs("## Quanto ele ocupa\n\nTexto.\n"), []);
    assert.deepEqual(faqPairs(""), []);
  });

  it("keeps a question with no answer out of the pair list", () => {
    assert.deepEqual(faqPairs("## Perguntas frequentes\n\n### Só a pergunta?\n"), []);
  });
});
