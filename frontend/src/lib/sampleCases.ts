import type { DemoCase } from "./types";

export const demoCases: DemoCase[] = [
  {
    id: "recognized",
    label: "Recognized charge",
    openingMessage: "I do not recognize this Netflix charge. Can you check it?",
    context: {
      customer_id: "cust_demo_001",
      account_currency: "USD",
      home_country: "US",
      transaction: {
        id: "txn_netflix_071",
        merchant_name: "Netflix",
        merchant_category: "streaming",
        amount: 15.99,
        currency: "USD",
        date: "2026-07-06",
        country: "US",
        recurring: true
      },
      known_merchants: [
        {
          merchant_name: "Netflix",
          aliases: ["Netflix.com", "Netflix Streaming"],
          typical_amount: 15.99,
          recurring: true
        }
      ],
      recent_charges: [
        { merchant_name: "Netflix", amount: 15.99, currency: "USD", date: "2026-06-06", country: "US" },
        { merchant_name: "Trader Joe's", amount: 64.14, currency: "USD", date: "2026-07-04", country: "US" }
      ],
      card_status: {
        lost_or_stolen_reported: false
      }
    }
  },
  {
    id: "ambiguous",
    label: "Ambiguous subscription",
    openingMessage: "I know I had a fitness app, but this FitPlus charge is more than usual.",
    context: {
      customer_id: "cust_demo_002",
      account_currency: "USD",
      home_country: "US",
      transaction: {
        id: "txn_fitplus_118",
        merchant_name: "FitPlus",
        merchant_category: "fitness",
        amount: 29.99,
        currency: "USD",
        date: "2026-07-05",
        country: "US",
        recurring: true
      },
      known_merchants: [
        {
          merchant_name: "FitPlus",
          aliases: ["FitPlus App", "FitPlus Monthly"],
          typical_amount: 9.99,
          recurring: true
        }
      ],
      recent_charges: [
        { merchant_name: "FitPlus", amount: 9.99, currency: "USD", date: "2026-06-05", country: "US" },
        { merchant_name: "Blue Bottle", amount: 6.5, currency: "USD", date: "2026-07-05", country: "US" }
      ],
      card_status: {
        lost_or_stolen_reported: false
      }
    }
  },
  {
    id: "likely-fraud",
    label: "Likely fraud",
    openingMessage: "My wallet went missing yesterday and now I see a foreign ATM withdrawal.",
    context: {
      customer_id: "cust_demo_003",
      account_currency: "USD",
      home_country: "US",
      transaction: {
        id: "txn_atm_443",
        merchant_name: "ATM Centro MX",
        merchant_category: "atm",
        amount: 420,
        currency: "MXN",
        date: "2026-07-06",
        country: "MX",
        recurring: false
      },
      known_merchants: [
        {
          merchant_name: "Chase ATM",
          aliases: ["JPMorgan ATM"],
          typical_amount: 80,
          recurring: false
        }
      ],
      recent_charges: [
        { merchant_name: "ATM Centro MX", amount: 420, currency: "MXN", date: "2026-07-06", country: "MX" },
        { merchant_name: "Farmacia Centro", amount: 88, currency: "MXN", date: "2026-07-06", country: "MX" },
        { merchant_name: "Tienda Norte", amount: 121, currency: "MXN", date: "2026-07-06", country: "MX" }
      ],
      card_status: {
        lost_or_stolen_reported: true,
        reported_at: "2026-07-06T14:12:00Z"
      }
    }
  }
];

