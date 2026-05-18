export default interface ASTNode {
    type: string;
    value?: string;
    children?: ASTNode[];
}