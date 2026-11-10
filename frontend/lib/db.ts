// MongoDB client used by the NextAuth adapter. Optional: when MONGODB_URI is not
// set, sign-in still works (JWT sessions) but users are not persisted.
import { MongoClient } from "mongodb"

const uri = process.env.MONGODB_URI

let client: MongoClient | null = null

if (uri) {
  if (process.env.NODE_ENV === "development") {
    // Reuse the client across hot reloads in development.
    const globalWithMongo = global as typeof globalThis & { _mongoClient?: MongoClient }
    if (!globalWithMongo._mongoClient) {
      globalWithMongo._mongoClient = new MongoClient(uri)
    }
    client = globalWithMongo._mongoClient
  } else {
    client = new MongoClient(uri)
  }
}

export default client
