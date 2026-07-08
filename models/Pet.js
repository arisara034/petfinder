const mongoose = require("mongoose")

const PetSchema = new mongoose.Schema({

name:String,
type:String,
location:String,

lat:Number,
lng:Number,

image:String,
poster:String,

createdAt:{
type:Date,
default:Date.now
}

})

module.exports = mongoose.model("Pet",PetSchema)