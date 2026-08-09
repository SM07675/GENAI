package com.genie.ai.core.database

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface ConversationDao {
    @Query("SELECT * FROM conversations ORDER BY timestamp ASC")
    fun getAllConversations(): Flow<List<ConversationEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(conversation: ConversationEntity)

    @Query("DELETE FROM conversations")
    suspend fun clearAll()
}

@Dao
interface TaskQueueDao {
    @Query("SELECT * FROM queued_tasks ORDER BY createdAt ASC")
    suspend fun getPendingTasks(): List<QueuedTaskEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun enqueue(task: QueuedTaskEntity)

    @Query("DELETE FROM queued_tasks WHERE id = :taskId")
    suspend fun removeTask(taskId: Long)

    @Query("DELETE FROM queued_tasks")
    suspend fun clearQueue()
}
