export default interface Grammar {
    nonTerminals: string[];
    terminals: string[];
    productions: Record<string, string[][]>;
    startSymbol: string;
}