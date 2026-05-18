import ASTNode from "./ast";
import { Step } from "./step";

export default interface ParseResult{
  steps: Step[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  table?: any;
  tree?: ASTNode;
  errors?: string[];
};