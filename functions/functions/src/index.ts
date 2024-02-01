import { region } from "firebase-functions";
import { firestore } from "firebase-admin";

export const backupFirestoreToStorage = region("asia-northeast1")
  .pubsub.schedule("0 0 * * *")
  .timeZone("Asia/Tokyo")
  .onRun(async () => {
    try {
      console.log("Exporting firestore...");
      const projectId = process.env.GCP_PROJECT || process.env.GCLOUD_PROJECT;
      const bucket = "gs://battonaiocr-backup";
      const client = new firestore.v1.FirestoreAdminClient();

      let responses = await client.exportDocuments({
        name: client.databasePath(projectId!, "(default)"),
        outputUriPrefix: bucket,
        collectionIds: [],
      });
      console.log("Exported");
      console.log(`Operation Name: ${responses[0].name}`);
    } catch (err) {
      console.error(err);
    }
  });
