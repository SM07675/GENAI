package com.genie.ai.core.database

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "queued_tasks")
data class QueuedTaskEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val intent: String,
    val payloadJson: String,
    val createdAt: Long = System.currentTimeMillis(),
    val isDangerous: Boolean = false
)
