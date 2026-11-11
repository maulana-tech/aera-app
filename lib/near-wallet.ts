/* Signing from the browser, for the people who hold the keys.
 *
 * The agent service only ever holds a function-call key on the vault: it can
 * ask for a payment, it cannot move money. Everything that moves money past
 * the caps (approve, reject, refund, unfreeze) and every customer payment is
 * signed here, in the person's own wallet, through NEAR Connect.
 *
 * Kept behind this small interface so the pages never import the wallet
 * library directly: it touches window, localStorage and IndexedDB and must not
 * load during a server render, and when it cannot load at all (blocked
 * iframes, no wallet installed) each call still has an exact near-cli-rs
 * command to run instead (`cliCommand`).
 */
import { teraToGas } from "near-api-js";

export type Network = "testnet" | "mainnet";

/** One function call on a contract, as signed from a wallet. */
export type ContractCall = {
  contract: string;
  method: string;
  args: Record<string, unknown>;
  /** yoctoNEAR, as a string */
  deposit: string;
  /** gas, in teragas */
  tgas: number;
};

export const ONE_YOCTO = "1";

/* ---------------------------------------------------------- the vault calls */

export const vault = {
  approve: (contract: string, requestId: string): ContractCall =>
    ({ contract, method: "approve", args: { request_id: requestId }, deposit: ONE_YOCTO, tgas: 30 }),
  reject: (contract: string, requestId: string, reason: string): ContractCall =>
    ({ contract, method: "reject", args: { request_id: requestId, reason }, deposit: ONE_YOCTO, tgas: 30 }),
  /** `amount` in token base units (USDC: 6 decimals). */
  refund: (contract: string, orderId: string, amount: string): ContractCall =>
    ({ contract, method: "refund", args: { order_id: orderId, amount }, deposit: ONE_YOCTO, tgas: 30 }),
  /** The vault takes a freeze from the owner, an approver or the agent, with no deposit. */
  freeze: (contract: string): ContractCall =>
    ({ contract, method: "freeze", args: {}, deposit: "0", tgas: 30 }),
  /** The owner writes the spending caps (token base units) to the vault. 1 yoctoNEAR, owner only. */
  setPolicy: (contract: string, perTxCap: string, dailyCap: string): ContractCall =>
    ({ contract, method: "set_policy", args: { per_tx_cap: perTxCap, daily_cap: dailyCap }, deposit: ONE_YOCTO, tgas: 30 }),
  /** Only the owner may resume, and the vault asks for the 1 yoctoNEAR proof of a full-access key. */
  unfreeze: (contract: string): ContractCall =>
    ({ contract, method: "unfreeze", args: {}, deposit: ONE_YOCTO, tgas: 30 }),
};

/** A customer's payment: USDC to the vault, with the order in `msg`. */
export const ftTransferCall = (token: string, receiverId: string, amount: string, msg: string): ContractCall =>
  ({ contract: token, method: "ft_transfer_call", args: { receiver_id: receiverId, amount, msg },
     deposit: ONE_YOCTO, tgas: 100 });

/* ------------------------------------------------------- the fallback, typed */

const shellQuote = (s: string) => `'${s.replace(/'/g, `'\\''`)}'`;

/** The same call as a near-cli-rs command, for when no wallet can be reached. */
export function cliCommand(call: ContractCall, network: Network, signer = "<your-account>"): string {
  const deposit = call.deposit === "0" ? "0 NEAR" : `${call.deposit} yoctoNEAR`;
  return [
    "near contract call-function as-transaction", call.contract, call.method,
    "json-args", shellQuote(JSON.stringify(call.args)),
    "prepaid-gas", shellQuote(`${call.tgas} Tgas`),
    "attached-deposit", shellQuote(deposit),
    "sign-as", signer,
    "network-config", network,
    "sign-with-keychain send",
  ].join(" ");
}

/* --------------------------------------------------------------- the wallet */

type Connector = import("@hot-labs/near-connect").NearConnector;

const connectors = new Map<Network, Promise<Connector>>();

/** One connector per network per page, made on first use and only in a browser. */
async function connector(network: Network): Promise<Connector> {
  if (typeof window === "undefined") throw new Error("a wallet can only be used in the browser");
  let c = connectors.get(network);
  if (!c) {
    c = (async () => {
      const { NearConnector } = await import("@hot-labs/near-connect");
      const nc = new NearConnector({
        network,
        features: { signAndSendTransaction: true, ...(network === "testnet" ? { testnet: true } : {}) },
        footerBranding: null,
      });
      await nc.whenManifestLoaded;
      return nc;
    })();
    connectors.set(network, c);
    c.catch(() => connectors.delete(network));
  }
  return c;
}

/** The account already connected on this network, or null. Never opens a dialog. */
export async function connectedAccount(network: Network): Promise<string | null> {
  try {
    const nc = await connector(network);
    const { accounts } = await nc.getConnectedWallet();
    return accounts[0]?.accountId ?? null;
  } catch {
    return null;
  }
}

/** Ask the person to pick a wallet and sign in. Returns the account id. */
export async function connectWallet(network: Network): Promise<string> {
  const nc = await connector(network);
  const wallet = await nc.connect();
  const accounts = await wallet.getAccounts({ network });
  const id = accounts[0]?.accountId;
  if (!id) throw new Error("the wallet returned no account");
  return id;
}

export async function disconnectWallet(network: Network): Promise<void> {
  const nc = await connector(network);
  await nc.disconnect();
}

/** Sign and send one call from the connected wallet. Returns the transaction hash. */
export async function signAndSend(call: ContractCall, network: Network): Promise<string> {
  const nc = await connector(network);
  const wallet = await nc.wallet();
  const outcome = await wallet.signAndSendTransaction({
    network,
    receiverId: call.contract,
    actions: [{
      type: "FunctionCall",
      params: {
        methodName: call.method,
        args: call.args,
        gas: teraToGas(call.tgas).toString(),
        deposit: call.deposit,
      },
    }],
  });
  const failure = (outcome?.status as { Failure?: unknown } | undefined)?.Failure;
  if (failure) throw new Error(`the transaction failed: ${JSON.stringify(failure).slice(0, 300)}`);
  return outcome?.transaction?.hash ?? outcome?.transaction_outcome?.id ?? "";
}

export const asNetwork = (n: string | null | undefined): Network => (n === "mainnet" ? "mainnet" : "testnet");
